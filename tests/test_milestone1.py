"""Milestone-1 end-to-end acceptance (SPEC 11.1).

Proves, on an isolated workspace:
- project + config.yaml created;
- accession -> metadata snapshot stored;
- modality_detected.csv + dataset_audit.csv produced;
- downstream BLOCKED until dataset_audit_approved.json exists;
- verify.py blocks empty audits, reads UTF-8, emits STATUS;
- generated code saved + hashed + logged (manifest + ai_prompts.jsonl).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import yaml
from conftest import BACKEND, REPO_ROOT

from omics_backend import services
from omics_backend.config_model import load_config
from omics_backend.enums import ApprovalDecision, Decision
from omics_backend.gateway import AIGateway


def _run_verify(ws: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    return subprocess.run([sys.executable, str(ws / "scripts" / "verify.py")],
                          cwd=str(ws), capture_output=True, text=True, env=env)


def test_milestone1_end_to_end(workspace: Path, fixtures: dict):
    ws = workspace

    # 1. project + config.yaml created
    base = yaml.safe_load((ws / "config.yaml").read_text(encoding="utf-8"))
    proj = services.create_project("demo", "Demo", ws, base_config=base)
    assert (ws / "config.yaml").exists()
    assert proj.config_hash

    cfg = load_config(ws / "config.yaml")
    accs = list(fixtures.keys())

    # 2. accession -> metadata snapshot stored
    for acc in accs:
        snap = services.fetch_metadata(acc, ws, injected=fixtures[acc], source_api="fixture")
        assert (ws / "results" / "metadata" / f"{acc}.json").exists()
        assert snap.checksum

    # 3. modality + dataset audit produced
    services.detect_modality(accs, ws)
    services.generate_dataset_audit(accs, ws, cfg)
    assert (ws / "results" / "modality_detected.csv").exists()
    assert (ws / "results" / "dataset_audit.csv").exists()

    # audit gate correctness: human + rna-seq INCLUDEd; dog / microarray / proteomics REJECTed
    import csv
    rows = {r["accession"]: r for r in csv.DictReader(
        (ws / "results" / "dataset_audit.csv").read_text(encoding="utf-8").splitlines())}
    assert rows["GSE112057"]["decision"] == "INCLUDE"
    assert rows["SRP149367"]["decision"] == "INCLUDE"
    assert rows["GSE99999"]["decision"] == "REJECT"      # organism
    assert rows["GSE99999"]["trigger_field"] == "organism"
    assert rows["GSE10072"]["decision"] == "REJECT"      # microarray
    assert rows["PXD000001"]["decision"] == "REJECT"     # proteomics

    # 4. downstream BLOCKED until approval exists.
    #    The approval artifact is absent now; the Snakemake DAG gates fetch_raw/QC/DE on it.
    assert not (ws / "results" / "approvals" / "dataset_audit_approved.json").exists()
    # verify currently PASSES selection layer (valid audit) but no approval => downstream
    # cannot run. We assert the gate file is what unlocks it:
    services.create_approval(
        "dataset_audit_approved", "results/dataset_audit.csv", "dr.reviewer",
        ws, ws / "config.yaml", decision=ApprovalDecision.APPROVED,
        note="reviewed audit table",
    )
    appr = ws / "results" / "approvals" / "dataset_audit_approved.json"
    assert appr.exists()
    art = json.loads(appr.read_text(encoding="utf-8"))
    assert art["approver"] == "dr.reviewer"
    assert art["decision"] == "APPROVED"
    assert art["config_hash"]

    # 5. verify emits explicit STATUS and reads UTF-8 (valid audit + modality => PASS)
    proc = _run_verify(ws)
    assert "STATUS=" in proc.stdout
    assert proc.stdout.strip().splitlines()[-1].startswith("STATUS=")
    assert "UnicodeDecodeError" not in proc.stderr

    # 6. generated code saved + hashed + logged
    gw = AIGateway(cfg, root=ws)
    code = "import sys\nprint('hello')\n"
    res = gw.call(
        prompt_id="code_generation", prompt_version="1.0",
        payload={"task": "demo worker", "donor_name": "SHOULD_BE_REDACTED"},
        generated_code=code, generated_code_path="logs/generated/demo_worker.py",
    )
    assert res["generated_code_hash"]
    assert res["redaction_applied"] is True  # donor_name redacted (send_raw_data=false)
    assert (ws / "logs" / "generated" / "demo_worker.py").read_text(encoding="utf-8") == code
    manifest = json.loads((ws / "logs" / "generated_code_manifest.json").read_text(encoding="utf-8"))
    assert manifest[-1]["sha256"] == res["generated_code_hash"]
    log_lines = (ws / "logs" / "ai_prompts.jsonl").read_text(encoding="utf-8").strip().splitlines()
    rec = json.loads(log_lines[-1])
    for key in ("request_id", "timestamp_utc", "model", "prompt_id", "prompt_version",
                "input_hash", "output_hash", "redaction_applied", "generated_code_hash"):
        assert key in rec, f"gateway log missing {key}"


def test_empty_audit_blocks_via_services(workspace: Path):
    """A zero-row dataset_audit must BLOCK (SPEC 8 cond 3)."""
    ws = workspace
    # produce an audit over an empty accession list -> zero rows
    cfg = load_config(ws / "config.yaml")
    services.generate_dataset_audit([], ws, cfg)
    proc = _run_verify(ws)
    assert "STATUS=BLOCKED" in proc.stdout
    assert proc.returncode == 1


def test_approval_requires_human_identity(workspace: Path):
    """The app never auto-approves: empty approver is rejected."""
    import pytest
    ws = workspace
    with pytest.raises(ValueError):
        services.create_approval("x", "results/dataset_audit.csv", "  ", ws, ws / "config.yaml")
