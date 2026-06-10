"""API contract smoke tests (SPEC 10) via FastAPI TestClient on an isolated workspace."""
from __future__ import annotations

import importlib
import os

import yaml
from conftest import REPO_ROOT


def _client(workspace):
    os.environ["OMICS_WORKSPACE"] = str(workspace)
    import omics_backend.app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient
    return TestClient(appmod.app)


def test_api_milestone1_flow(workspace, fixtures):
    client = _client(workspace)

    base = yaml.safe_load((workspace / "config.yaml").read_text(encoding="utf-8"))
    r = client.post("/projects", json={"id": "demo", "name": "Demo", "config": base})
    assert r.status_code == 200, r.text
    assert r.json()["config_hash"]

    accs = list(fixtures.keys())
    r = client.post("/projects/demo/accessions", json={"accessions": accs})
    assert r.status_code == 200
    assert len(r.json()["accessions"]) == len(accs)

    for acc in accs:
        r = client.post("/projects/demo/metadata:fetch",
                        json={"accession": acc, "injected": fixtures[acc], "source_api": "fixture"})
        assert r.status_code == 200, r.text

    r = client.post("/projects/demo/modality:detect", json={"accessions": accs})
    assert r.status_code == 200

    r = client.post("/projects/demo/dataset-audit", json={"accessions": accs})
    assert r.status_code == 200

    # run-status before approval: verifier runs and returns an explicit status
    r = client.get("/projects/demo/run-status")
    assert r.status_code == 200
    assert r.json()["status"] in ("PASS", "NEEDS_REVIEW", "BLOCKED")

    # approval requires a human identity
    r = client.post("/projects/demo/approvals", json={
        "artifact": "dataset_audit_approved", "approves": "results/dataset_audit.csv",
        "approver": "dr.reviewer"})
    assert r.status_code == 200, r.text
    assert r.json()["decision"] == "APPROVED"

    # empty approver rejected (no auto-approval)
    r = client.post("/projects/demo/approvals", json={
        "artifact": "x", "approves": "results/dataset_audit.csv", "approver": ""})
    assert r.status_code == 400

    # qc dashboard aggregates audits
    r = client.get("/projects/demo/qc-dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["audits"]["dataset_audit.csv"]["present"] is True
    assert "dataset_audit_approved.json" in body["approvals"]
