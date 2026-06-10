"""FastAPI app — desktop<->backend contract (SPEC 10).

The backend is the only component that holds vendor credentials and the only path to
vendor models. Endpoints are typed by the Pydantic models in models.py. Projects live
under a workspace root (default: the repo root); each project's artifacts live in its
root_dir.

Run:  uvicorn omics_backend.app:app --host 127.0.0.1 --port 8765
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from . import services
from .config_model import OmicsConfig, load_config
from .enums import ApprovalDecision, Status
from .gateway import AIGateway
from .models import ApprovalArtifact, MetadataSnapshot, Project, RunStatus

# Workspace root: where projects + config live. Default to repo root (two levels up
# from this file: apps/backend/omics_backend/ -> repo root).
WORKSPACE = Path(os.environ.get("OMICS_WORKSPACE", Path(__file__).resolve().parents[3]))

app = FastAPI(title="AI-Assisted Omics Backend", version="0.1.0")


def _project_root(project_id: str) -> Path:
    # Single-workspace mode: the project operates on the workspace root. Multi-project
    # mode would map project_id -> WORKSPACE/projects/<id>.
    return WORKSPACE


def _config(project_id: str) -> OmicsConfig:
    cfg_path = _project_root(project_id) / "config.yaml"
    if not cfg_path.exists():
        raise HTTPException(404, f"config.yaml not found for project {project_id}")
    return load_config(cfg_path)


# --- request bodies ------------------------------------------------------------

class CreateProjectBody(BaseModel):
    id: str
    name: str
    config: Optional[dict] = None  # full config dict; if absent, copy current config.yaml


class AccessionsBody(BaseModel):
    accessions: list[str] = Field(min_length=1)


class MetadataFetchBody(BaseModel):
    accession: str
    injected: Optional[dict[str, str]] = None  # offline/fixture metadata
    source_api: str = "injected"


class ModalityDetectBody(BaseModel):
    accessions: list[str] = Field(min_length=1)


class DatasetAuditBody(BaseModel):
    accessions: list[str] = Field(min_length=1)


class ApprovalBody(BaseModel):
    artifact: str
    approves: str
    approver: str
    decision: ApprovalDecision = ApprovalDecision.APPROVED
    note: str = ""


class CodeReviewBody(BaseModel):
    language: str
    code: str
    context: str = ""


# --- endpoints (SPEC 10) -------------------------------------------------------

@app.post("/projects", response_model=Project)
def create_project(body: CreateProjectBody) -> Project:
    root = _project_root(body.id)
    template = None if body.config is not None else (root / "config.yaml")
    if template is not None and not Path(template).exists():
        raise HTTPException(400, "no config provided and no existing config.yaml to copy")
    return services.create_project(
        body.id, body.name, root,
        base_config=body.config,
        template_config_path=template,
    )


@app.get("/projects/{project_id}", response_model=Project)
def get_project(project_id: str) -> Project:
    root = _project_root(project_id)
    cfg = _config(project_id)
    from .config_model import config_hash
    return Project(
        id=project_id, name=cfg.project.name, root_dir=str(root),
        config_path="config.yaml", config_hash=config_hash(root / "config.yaml"),
    )


@app.post("/projects/{project_id}/accessions")
def add_accessions(project_id: str, body: AccessionsBody) -> dict:
    from .namespaces import classify_namespace
    out = []
    for acc in body.accessions:
        repo, _mod, valid = classify_namespace(acc)
        out.append({"id": acc, "repository": repo.value, "namespace_valid": valid})
    return {"accessions": out}


@app.post("/projects/{project_id}/metadata:fetch", response_model=MetadataSnapshot)
def fetch_metadata(project_id: str, body: MetadataFetchBody) -> MetadataSnapshot:
    root = _project_root(project_id)
    return services.fetch_metadata(
        body.accession, root, injected=body.injected, source_api=body.source_api,
    )


@app.post("/projects/{project_id}/modality:detect")
def detect_modality(project_id: str, body: ModalityDetectBody) -> dict:
    root = _project_root(project_id)
    out = services.detect_modality(body.accessions, root)
    return {"modality_detected": str(out.relative_to(root))}


@app.post("/projects/{project_id}/dataset-audit")
def dataset_audit(project_id: str, body: DatasetAuditBody) -> dict:
    root = _project_root(project_id)
    cfg = _config(project_id)
    out = services.generate_dataset_audit(body.accessions, root, cfg)
    return {"dataset_audit": str(out.relative_to(root))}


@app.post("/projects/{project_id}/approvals", response_model=ApprovalArtifact)
def create_approval(project_id: str, body: ApprovalBody) -> ApprovalArtifact:
    root = _project_root(project_id)
    cfg_path = root / "config.yaml"
    try:
        out = services.create_approval(
            body.artifact, body.approves, body.approver, root, cfg_path,
            decision=body.decision, note=body.note,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return ApprovalArtifact.model_validate(json.loads(out.read_text(encoding="utf-8")))


@app.get("/projects/{project_id}/run-status", response_model=RunStatus)
def run_status(project_id: str) -> RunStatus:
    root = _project_root(project_id)
    # Run the verifier (it writes results/run_status.json and emits STATUS).
    proc = subprocess.run(
        [sys.executable, str(root / "scripts" / "verify.py")],
        cwd=str(root), capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(root / "apps" / "backend")},
    )
    status_path = root / "results" / "run_status.json"
    if status_path.exists():
        return RunStatus.model_validate(json.loads(status_path.read_text(encoding="utf-8")))
    # Fall back to parsing STATUS= from stdout.
    status = Status.BLOCKED
    for line in proc.stdout.splitlines():
        if line.startswith("STATUS="):
            status = Status(line.split("=", 1)[1].strip())
    return RunStatus(status=status, stage="final_verifier", details=[proc.stdout[-500:]])


@app.get("/projects/{project_id}/qc-dashboard")
def qc_dashboard(project_id: str) -> dict:
    """Aggregate audit-table summaries for the dashboard."""
    import csv
    root = _project_root(project_id)
    results = root / "results"

    def _count(name: str) -> dict:
        p = results / name
        if not p.exists():
            return {"present": False, "rows": 0}
        rows = list(csv.DictReader(p.read_text(encoding="utf-8").splitlines()))
        return {"present": True, "rows": len(rows)}

    audits = ["dataset_audit.csv", "modality_detected.csv", "sample_qc_audit.csv",
              "feature_qc_audit.csv", "cell_qc_audit.csv", "doublet_audit.csv",
              "outlier_audit.csv", "missingness_audit.csv", "imputation_audit.csv"]
    summary = {name: _count(name) for name in audits}
    approved = sorted(p.name for p in (results / "approvals").glob("*.json")) if (results / "approvals").exists() else []
    return {"audits": summary, "approvals": approved}


@app.post("/ai/code-review")
def ai_code_review(body: CodeReviewBody) -> dict:
    """Submit code for AI review (advisory). Logged via the gateway; secrets stay in
    the backend. Without credentials the gateway runs in stub mode but still records
    full provenance."""
    cfg = _config("default") if (WORKSPACE / "config.yaml").exists() else None
    if cfg is None:
        raise HTTPException(400, "no config.yaml in workspace")
    gw = AIGateway(cfg, root=WORKSPACE)
    result = gw.call(
        prompt_id="code_review", prompt_version="1.0",
        payload={"language": body.language, "code": body.code, "context": body.context},
    )
    return result
