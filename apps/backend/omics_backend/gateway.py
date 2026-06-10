"""AI gateway — the ONLY path to vendor models (SPEC 10.1).

Responsibilities:
- Hold/read vendor credentials in the BACKEND only (OS keychain in dev, OAuth/OIDC in
  prod). Never expose them to the renderer.
- Redact sensitive metadata before any prompt; never send raw sequence / full matrices
  / patient metadata unless config `ai.send_raw_data` is true.
- Log EVERY call to logs/ai_prompts.jsonl with model, prompt id+version, request/
  response ids, timestamp, input/output hashes, redaction flag, generated-code hash.
- Persist generated code to logs/generated_code_manifest.json (path + sha256 + linkage).

Without credentials the gateway runs in STUB mode: it does not call a vendor, but it
STILL records the full provenance contract (provider ids = null, mode = "stub"). Live
calls require credentials supplied to the backend (see get_credential).

Stdlib only (no vendor SDK import here; live transport is added where credentials exist).
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Optional

from . import provenance as prov
from .config_model import OmicsConfig

# Fields that must be redacted from any payload before it leaves the backend, unless
# ai.send_raw_data is explicitly enabled. Conservative deny-list of identifying keys.
_REDACT_KEYS = re.compile(
    r"(patient|subject|donor|mrn|name|email|dob|birth|address|phone|ssn|sample_raw|sequence|matrix)",
    re.I,
)


def get_credential(provider: str) -> Optional[str]:
    """Read a vendor credential from the backend environment / OS keychain (dev mode).

    Returns None when no credential is configured -> gateway runs in stub mode.
    NEVER returns to the renderer; this is backend-internal.
    """
    env_key = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY"}.get(provider.lower())
    if env_key and os.environ.get(env_key):
        return os.environ[env_key]
    # Dev-mode OS keychain lookup would go here (e.g., `keyring.get_password`). Absent
    # a keychain entry, return None so callers degrade to stub mode.
    return None


def redact(payload: dict, send_raw_data: bool) -> tuple[dict, bool]:
    """Return (redacted_payload, redaction_applied). Drops identifying keys unless raw
    data is explicitly enabled."""
    if send_raw_data:
        return payload, False
    applied = False
    out: dict = {}
    for k, v in payload.items():
        if _REDACT_KEYS.search(k):
            out[k] = "[REDACTED]"
            applied = True
        elif isinstance(v, dict):
            sub, sub_applied = redact(v, send_raw_data)
            out[k] = sub
            applied = applied or sub_applied
        else:
            out[k] = v
    return out, applied


class AIGateway:
    def __init__(self, cfg: OmicsConfig, root: str | Path = "."):
        self.cfg = cfg
        self.root = Path(root)
        self.log_path = self.root / cfg.ai.gateway_log
        self.manifest_path = self.root / cfg.ai.generated_code_manifest

    def _credential(self) -> Optional[str]:
        return get_credential(self.cfg.ai.provider)

    def call(
        self,
        prompt_id: str,
        prompt_version: str,
        payload: dict,
        *,
        system: Optional[str] = None,
        generated_code: Optional[str] = None,
        generated_code_path: Optional[str] = None,
    ) -> dict:
        """Execute (or stub) one model call and record full provenance.

        With a backend credential the call goes live (OpenAI Responses API or Anthropic
        Messages API per `ai.provider`); without one it runs in stub mode. Either way the
        full provenance row is logged.
        """
        request_id = prov.new_id("req")
        redacted_payload, redaction_applied = redact(payload, self.cfg.ai.send_raw_data)
        input_hash = prov.sha256_text(json.dumps(redacted_payload, sort_keys=True, ensure_ascii=False))

        cred = self._credential()
        provider_request_id = None
        provider_response_id = None
        output_text = ""
        error = None
        if cred:
            try:
                output_text, provider_request_id, provider_response_id = self._live_call(
                    cred, redacted_payload, system,
                )
                mode = "live"
            except Exception as e:  # noqa: BLE001 - record failure, never crash the gate
                mode = "live_error"
                error = f"{type(e).__name__}: {e}"
        else:
            mode = "stub"

        output_hash = prov.sha256_text(output_text)
        generated_code_hash = None
        if generated_code is not None:
            generated_code_hash = prov.sha256_text(generated_code)
            if generated_code_path:
                p = self.root / generated_code_path
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text(generated_code, encoding="utf-8")
            prov.append_manifest(self.manifest_path, {
                "request_id": request_id,
                "timestamp_utc": prov.utcnow(),
                "prompt_id": prompt_id,
                "prompt_version": prompt_version,
                "path": generated_code_path,
                "sha256": generated_code_hash,
                "mode": mode,
            })

        prov.append_jsonl(self.log_path, {
            "request_id": request_id,
            "timestamp_utc": prov.utcnow(),
            "model": self.cfg.ai.model,
            "provider": self.cfg.ai.provider,
            "prompt_id": prompt_id,
            "prompt_version": prompt_version,
            "provider_request_id": provider_request_id,
            "provider_response_id": provider_response_id,
            "input_hash": input_hash,
            "output_hash": output_hash,
            "redaction_applied": redaction_applied,
            "generated_code_hash": generated_code_hash,
            "mode": mode,
            "error": error,
        })

        return {
            "request_id": request_id,
            "mode": mode,
            "redaction_applied": redaction_applied,
            "output": output_text,
            "generated_code_hash": generated_code_hash,
            "error": error,
        }

    def _live_call(
        self, cred: str, payload: dict, system: Optional[str],
    ) -> tuple[str, Optional[str], Optional[str]]:
        """Dispatch a live vendor call. Returns (output_text, request_id, response_id).

        Vendor SDKs are imported lazily so stub mode never requires them.
        """
        user_input = json.dumps(payload, ensure_ascii=False)
        if self.cfg.ai.provider == "openai":
            from openai import OpenAI  # lazy import

            client = OpenAI(api_key=cred)
            kwargs = {"model": self.cfg.ai.model, "input": user_input}
            if system:
                kwargs["instructions"] = system
            resp = client.responses.create(**kwargs)
            req_id = getattr(resp, "_request_id", None)
            return (getattr(resp, "output_text", "") or "", req_id, getattr(resp, "id", None))

        if self.cfg.ai.provider == "anthropic":
            from anthropic import Anthropic  # lazy import

            client = Anthropic(api_key=cred)
            kwargs = {
                "model": self.cfg.ai.model,
                "max_tokens": 2048,
                "messages": [{"role": "user", "content": user_input}],
            }
            if system:
                kwargs["system"] = system
            resp = client.messages.create(**kwargs)
            text = "".join(getattr(b, "text", "") for b in resp.content)
            req_id = getattr(resp, "_request_id", None)
            return (text, req_id, getattr(resp, "id", None))

        raise ValueError(f"unsupported provider: {self.cfg.ai.provider}")
