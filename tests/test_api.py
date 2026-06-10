"""API contract tests (SPEC 10) via FastAPI TestClient against a multi-project workspace.

Network is disabled (OMICS_OFFLINE=1) so metadata:fetch uses offline namespace-only
snapshots and the suite stays deterministic. The INCLUDE/REJECT gate logic is covered
deterministically by test_milestone1.py via injected fixtures.
"""
from __future__ import annotations

import importlib
import os


def _client(workspace):
    os.environ["OMICS_WORKSPACE"] = str(workspace)
    os.environ["OMICS_OFFLINE"] = "1"
    import omics_backend.app as appmod
    importlib.reload(appmod)
    from fastapi.testclient import TestClient
    return TestClient(appmod.app)


def test_api_multiproject_flow(workspace):
    client = _client(workspace)

    # create project (client-shaped body)
    r = client.post("/projects", json={
        "name": "Adipose CVD 2026", "allowed_organisms": ["Homo sapiens"],
        "required_assay": "bulk_transcriptomics", "min_n_total": 6})
    assert r.status_code == 200, r.text
    proj = r.json()
    pid = proj["id"]
    assert proj["config_snapshot_ref"]
    assert proj["name"] == "Adipose CVD 2026"

    # round-trip GET
    assert client.get(f"/projects/{pid}").status_code == 200
    assert client.get("/projects/does-not-exist").status_code == 404

    # accessions
    r = client.post(f"/projects/{pid}/accessions", json={"accessions": ["GSE112057", "PXD000001"]})
    assert r.status_code == 200, r.text
    accs = r.json()
    assert {a["id"] for a in accs} == {"GSE112057", "PXD000001"}
    assert all(a["project_id"] == pid for a in accs)

    # metadata fetch (offline namespace-only)
    r = client.post(f"/projects/{pid}/metadata:fetch")
    assert r.status_code == 200, r.text
    snaps = r.json()
    assert len(snaps) == 2
    assert all("raw_fields" in s and "checksum" in s for s in snaps)

    # modality detect -> rows
    r = client.post(f"/projects/{pid}/modality:detect")
    assert r.status_code == 200
    mods = {m["accession"]: m for m in r.json()}
    assert mods["PXD000001"]["modality"] == "proteomics_ms"

    # dataset audit -> client-shaped rows
    r = client.post(f"/projects/{pid}/dataset-audit")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert all({"accession", "decision", "platform_gpl", "trigger_field"} <= set(row) for row in rows)

    # run status -> valid enum
    r = client.get(f"/projects/{pid}/run-status")
    assert r.status_code == 200
    assert r.json()["status"] in ("PASS", "NEEDS_REVIEW", "BLOCKED")
    assert r.json()["created_utc"]

    # approval requires a human identity (no auto-approve)
    r = client.post(f"/projects/{pid}/approvals", json={
        "approves": "results/dataset_audit.csv", "approver": "", "decision": "APPROVED"})
    assert r.status_code == 400
    r = client.post(f"/projects/{pid}/approvals", json={
        "approves": "results/dataset_audit.csv", "approver": "dr.reviewer", "decision": "APPROVED"})
    assert r.status_code == 200, r.text
    assert r.json()["decision"] == "APPROVED"
    assert r.json()["artifact"] == "dataset_audit_approved"

    # qc dashboard shape
    r = client.get(f"/projects/{pid}/qc-dashboard")
    assert r.status_code == 200
    body = r.json()
    assert body["dataset_audit_summary"]["total"] == 2
    assert "modality_summary" in body
