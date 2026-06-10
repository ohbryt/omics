"""Shared test fixtures: import path + isolated workspace builder."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / "apps" / "backend"

# Make omics_backend importable.
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))


@pytest.fixture()
def fixtures() -> dict:
    data = json.loads((REPO_ROOT / "tests" / "fixtures" / "accessions.json").read_text(encoding="utf-8"))
    # Drop the top-level _comment and, within each accession, any _-prefixed annotation
    # keys (e.g. _expect_decision) so only real metadata fields are injected.
    out = {}
    for acc, fields in data.items():
        if acc.startswith("_"):
            continue
        out[acc] = {k: v for k, v in fields.items() if not k.startswith("_")}
    return out


@pytest.fixture()
def workspace(tmp_path: Path) -> Path:
    """An isolated workspace: real config.yaml + scripts/verify.py copied into tmp.

    Running verify.py from here keeps ROOT=tmp while PYTHONPATH (set by the test) points
    at the real backend for strict schema validation.
    """
    (tmp_path / "scripts").mkdir(parents=True)
    (tmp_path / "results" / "approvals").mkdir(parents=True)
    (tmp_path / "results" / "metadata").mkdir(parents=True)
    (tmp_path / "logs").mkdir(parents=True)
    (tmp_path / "data").mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "config.yaml", tmp_path / "config.yaml")
    shutil.copy2(REPO_ROOT / "scripts" / "verify.py", tmp_path / "scripts" / "verify.py")
    return tmp_path
