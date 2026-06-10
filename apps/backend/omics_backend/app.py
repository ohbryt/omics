"""FastAPI app — desktop<->backend contract (SPEC 10).

The backend is the only component that holds vendor credentials and the only path to
vendor models. Projects live under WORKSPACE/projects/<id>/, each with its own
config.yaml, results/, logs/, data/. Response shapes match the desktop client.

Run:  uvicorn omics_backend.app:app --host 127.0.0.1 --port 8765
Env:  OMICS_WORKSPACE (workspace root; defaults to repo root)
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from . import provenance as prov
from . import services
from .config_model import config_hash, load_config
from .enums import ApprovalDecision
from .gateway import AIGateway

REPO_ROOT = Path(__file__).resolve().parents[3]
WORKSPACE = Path(os.environ.get("OMICS_WORKSPACE", REPO_ROOT))
VERIFY_PY = REPO_ROOT / "scripts" / "verify.py"

app = FastAPI(title="AI-Assisted Omics Backend", version="0.1.0")
# The renderer runs on a local origin (vite dev / file://); allow local calls.
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)


def _dir(project_id: str) -> Path:
    d = services.project_dir(WORKSPACE, project_id)
    if not (d / "config.yaml").exists():
        raise HTTPException(404, f"project not found: {project_id}")
    return d


def _project_record(d: Path) -> dict:
    rec = d / "project.json"
    if rec.exists():
        return json.loads(rec.read_text(encoding="utf-8"))
    cfg = load_config(d / "config.yaml")
    return {"id": cfg.project.id, "name": cfg.project.name,
            "created_utc": cfg.project.created_utc or "", "root_dir": str(d)}


# --- request bodies (match desktop client) -------------------------------------

class CreateProjectBody(BaseModel):
    name: str
    allowed_organisms: Optional[list[str]] = None
    required_assay: Optional[str] = None
    min_n_total: Optional[int] = None
    seed: Optional[int] = None


class AddAccessionsBody(BaseModel):
    accessions: list[str] = Field(min_length=1)


class CreateApprovalBody(BaseModel):
    approves: str
    approver: str
    decision: ApprovalDecision = ApprovalDecision.APPROVED
    note: Optional[str] = None


class AiCodeReviewBody(BaseModel):
    code: str
    context: Optional[str] = None


# --- endpoints (SPEC 10) -------------------------------------------------------

@app.post("/projects")
def create_project(body: CreateProjectBody) -> dict:
    proj = services.create_project_from_inputs(
        body.name, WORKSPACE,
        allowed_organisms=body.allowed_organisms,
        required_assay=body.required_assay,
        min_n_total=body.min_n_total,
        seed=body.seed,
    )
    d = services.project_dir(WORKSPACE, proj.id)
    rec = {"id": proj.id, "name": proj.name, "created_utc": proj.created_utc,
           "root_dir": str(d), "config_snapshot_ref": proj.config_hash}
    (d / "project.json").write_text(json.dumps(rec, indent=2), encoding="utf-8")
    return rec


@app.get("/projects/{project_id}")
def get_project(project_id: str) -> dict:
    d = _dir(project_id)
    rec = _project_record(d)
    rec["config_snapshot_ref"] = config_hash(d / "config.yaml")
    rec["root_dir"] = str(d)
    return rec


@app.post("/projects/{project_id}/accessions")
def add_accessions(project_id: str, body: AddAccessionsBody) -> list[dict]:
    d = _dir(project_id)
    entries = services.add_accessions(d, body.accessions)
    return [{**e, "project_id": project_id} for e in entries]


@app.post("/projects/{project_id}/metadata:fetch")
def fetch_metadata(project_id: str) -> list[dict]:
    d = _dir(project_id)
    if not services.list_accessions(d):
        raise HTTPException(400, "no accessions added to this project yet")
    online = os.environ.get("OMICS_OFFLINE") != "1"
    return services.fetch_project_metadata(d, online=online)


@app.post("/projects/{project_id}/modality:detect")
def detect_modality(project_id: str) -> list[dict]:
    d = _dir(project_id)
    accs = services.list_accessions(d)
    services.detect_modality(accs, d)
    rows = list(_read_csv(d / "results" / "modality_detected.csv"))
    return [{"accession": r["accession"], "modality": r["detected_modality"],
             "confidence": r["confidence"]} for r in rows]


@app.post("/projects/{project_id}/dataset-audit")
def dataset_audit(project_id: str) -> list[dict]:
    d = _dir(project_id)
    cfg = load_config(d / "config.yaml")
    accs = services.list_accessions(d)
    services.generate_dataset_audit(accs, d, cfg)
    out = []
    for r in _read_csv(d / "results" / "dataset_audit.csv"):
        out.append({
            "accession": r["accession"],
            "organism_verbatim": r["organism_verbatim"],
            "platform_gpl": r.get("platform_GPL") or None,
            "gdstype": r.get("gdstype") or None,
            "assay_detected": r.get("assay_detected") or None,
            "n_total": int(r["n_total"]) if r.get("n_total") else None,
            "n_case": int(r["n_case"]) if r.get("n_case") else None,
            "n_control": int(r["n_control"]) if r.get("n_control") else None,
            "tissue": r.get("tissue") or None,
            "decision": r["decision"],
            "trigger_field": r.get("trigger_field") or None,
            "trigger_value": r.get("trigger_value") or None,
        })
    return out


@app.post("/projects/{project_id}/approvals")
def create_approval(project_id: str, body: CreateApprovalBody) -> dict:
    d = _dir(project_id)
    # derive artifact name from the path being approved
    stem = Path(body.approves).stem  # e.g. dataset_audit
    artifact = f"{stem}_approved"
    try:
        out = services.create_approval(
            artifact, body.approves, body.approver, d, d / "config.yaml",
            decision=body.decision, note=body.note or "",
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return json.loads(out.read_text(encoding="utf-8"))


@app.get("/projects/{project_id}/run-status")
def run_status(project_id: str) -> dict:
    d = _dir(project_id)
    env = {**os.environ, "OMICS_ROOT": str(d), "PYTHONPATH": str(REPO_ROOT / "apps" / "backend")}
    subprocess.run([sys.executable, str(VERIFY_PY)], cwd=str(d), capture_output=True,
                   text=True, env=env)
    sp = d / "results" / "run_status.json"
    if sp.exists():
        rs = json.loads(sp.read_text(encoding="utf-8"))
        return {"status": rs["status"], "stage": rs.get("stage", "final_verifier"),
                "checks_passed": rs.get("checks_passed", 0),
                "checks_failed": rs.get("checks_failed", 0),
                "details": rs.get("details", []),
                "created_utc": rs.get("created_utc", prov.utcnow())}
    return {"status": "BLOCKED", "stage": "final_verifier", "checks_passed": 0,
            "checks_failed": 1, "details": ["verifier produced no run_status.json"],
            "created_utc": prov.utcnow()}


@app.get("/projects/{project_id}/qc-dashboard")
def qc_dashboard(project_id: str) -> dict:
    d = _dir(project_id)
    return services.build_qc_dashboard(d, project_id)


@app.post("/ai/code-review")
def ai_code_review(body: AiCodeReviewBody) -> dict:
    cfg = load_config(WORKSPACE / "config.yaml") if (WORKSPACE / "config.yaml").exists() else None
    if cfg is None:
        # fall back to any project config so the gateway has a model/provider
        raise HTTPException(400, "no workspace config.yaml for the AI gateway")
    gw = AIGateway(cfg, root=WORKSPACE)
    res = gw.call(prompt_id="code_review", prompt_version="1.0",
                  payload={"code": body.code, "context": body.context or ""})
    findings = []
    if res["mode"] in ("stub", "live_error"):
        findings.append({"severity": "info", "line": None,
                         "message": f"AI gateway in '{res['mode']}' mode "
                                    "(set OPENAI_API_KEY/ANTHROPIC_API_KEY in the backend for live review)."})
    return {"request_id": res["request_id"], "model": cfg.ai.model,
            "prompt_id": "code_review", "findings": findings,
            "generated_code_hash": res.get("generated_code_hash"),
            "timestamp_utc": prov.utcnow()}


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "workspace": str(WORKSPACE)}


# --- helpers -------------------------------------------------------------------

def _read_csv(path: Path):
    import csv
    if not path.exists():
        return []
    return list(csv.DictReader(path.read_text(encoding="utf-8").splitlines()))
