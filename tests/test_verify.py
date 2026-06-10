"""Verifier behavior tests (SPEC 8): UTF-8 reads, empty-audit block, explicit STATUS."""
from __future__ import annotations

import csv
import os
import subprocess
import sys
from pathlib import Path

from conftest import BACKEND


def run_verify(workspace: Path) -> subprocess.CompletedProcess:
    env = {**os.environ, "PYTHONPATH": str(BACKEND)}
    return subprocess.run(
        [sys.executable, str(workspace / "scripts" / "verify.py")],
        cwd=str(workspace), capture_output=True, text=True, env=env,
    )


def write_csv(path: Path, cols: list[str], rows: list[dict]):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)


def test_empty_audit_blocks(workspace: Path):
    # only a header, no rows -> BLOCKED (condition 3)
    write_csv(workspace / "results" / "dataset_audit.csv",
              ["accession", "organism_verbatim", "assay_detected", "n_total", "decision"], [])
    proc = run_verify(workspace)
    assert "STATUS=BLOCKED" in proc.stdout, proc.stdout
    assert proc.returncode == 1
    # run_status.json written as UTF-8 with explicit status
    rs = (workspace / "results" / "run_status.json")
    assert rs.exists()


def test_missing_audit_blocks(workspace: Path):
    proc = run_verify(workspace)  # no dataset_audit.csv at all
    assert "STATUS=BLOCKED" in proc.stdout, proc.stdout
    assert proc.returncode == 1


def test_valid_audit_passes(workspace: Path):
    cols = ["accession", "organism_verbatim", "platform_GPL", "gdstype", "assay_detected",
            "n_total", "n_case", "n_control", "tissue", "decision", "trigger_field", "trigger_value"]
    write_csv(workspace / "results" / "dataset_audit.csv", cols, [
        {"accession": "GSE112057", "organism_verbatim": "Homo sapiens", "platform_GPL": "GPL11154",
         "gdstype": "", "assay_detected": "rna-seq", "n_total": "12", "n_case": "6", "n_control": "6",
         "tissue": "blood", "decision": "INCLUDE", "trigger_field": "", "trigger_value": ""},
    ])
    write_csv(workspace / "results" / "modality_detected.csv",
              ["accession", "repository", "platform_instrument", "detected_modality",
               "evidence_field", "evidence_value", "confidence"],
              [{"accession": "GSE112057", "repository": "GEO", "platform_instrument": "",
                "detected_modality": "bulk_transcriptomics", "evidence_field": "structured_metadata",
                "evidence_value": "rna-seq", "confidence": "high"}])
    proc = run_verify(workspace)
    assert "STATUS=PASS" in proc.stdout, proc.stdout
    assert proc.returncode == 0


def test_organism_violation_blocks(workspace: Path):
    cols = ["accession", "organism_verbatim", "assay_detected", "n_total", "decision",
            "trigger_field", "trigger_value"]
    write_csv(workspace / "results" / "dataset_audit.csv", cols, [
        {"accession": "GSE99999", "organism_verbatim": "Canis lupus familiaris",
         "assay_detected": "rna-seq", "n_total": "10", "decision": "INCLUDE",
         "trigger_field": "", "trigger_value": ""},
    ])
    proc = run_verify(workspace)
    assert "STATUS=BLOCKED" in proc.stdout, proc.stdout
    assert "[c4]" in proc.stdout


def test_utf8_read_of_non_ascii_audit(workspace: Path):
    # A non-ASCII organism string must be read without a decode crash.
    cols = ["accession", "organism_verbatim", "assay_detected", "n_total", "decision",
            "trigger_field", "trigger_value"]
    p = workspace / "results" / "dataset_audit.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerow({"accession": "GSE1", "organism_verbatim": "Mus musculus — strain",
                    "assay_detected": "rna-seq", "n_total": "6", "decision": "REJECT",
                    "trigger_field": "organism", "trigger_value": "strain note"})
    proc = run_verify(workspace)
    # REJECT row, no INCLUDE -> not a c4 violation; should not crash on the em-dash.
    assert "STATUS=" in proc.stdout
    assert "UnicodeDecodeError" not in proc.stderr
