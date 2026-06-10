"""Config validation tests (SPEC 5)."""
from __future__ import annotations

import pytest
import yaml
from pydantic import ValidationError

from omics_backend.config_model import OmicsConfig, load_config


def test_repo_config_is_valid():
    from conftest import REPO_ROOT
    cfg = load_config(REPO_ROOT / "config.yaml")
    assert cfg.project.required_assay == "rna-seq"
    assert "Homo sapiens" in cfg.project.allowed_organisms
    assert cfg.fdr.scope == "genome_wide"
    assert cfg.ai.send_raw_data is False  # raw data off by default (SPEC 10.1)


def test_missing_required_section_blocks():
    with pytest.raises(ValidationError):
        OmicsConfig.model_validate({})  # no project section


def test_bad_assay_rejected():
    base = {
        "project": {
            "id": "x", "name": "x", "allowed_organisms": ["Homo sapiens"],
            "required_assay": "telepathy", "min_n_total": 1,
        }
    }
    with pytest.raises(ValidationError):
        OmicsConfig.model_validate(base)


def test_fdr_scope_must_be_genome_wide():
    base = {
        "project": {
            "id": "x", "name": "x", "allowed_organisms": ["Homo sapiens"],
            "required_assay": "rna-seq", "min_n_total": 1,
        },
        "fdr": {"scope": "within_gene_set"},
    }
    with pytest.raises(ValidationError):
        OmicsConfig.model_validate(base)


def test_unknown_key_forbidden():
    base = {
        "project": {
            "id": "x", "name": "x", "allowed_organisms": ["Homo sapiens"],
            "required_assay": "rna-seq", "min_n_total": 1,
        },
        "bogus_section": {"a": 1},
    }
    with pytest.raises(ValidationError):
        OmicsConfig.model_validate(base)


def test_integration_method_enum():
    base = {
        "project": {
            "id": "x", "name": "x", "allowed_organisms": ["Homo sapiens"],
            "required_assay": "rna-seq", "min_n_total": 1,
        },
        "integration": {"method": "not_a_method"},
    }
    with pytest.raises(ValidationError):
        OmicsConfig.model_validate(base)
    # null is allowed
    base["integration"]["method"] = None
    OmicsConfig.model_validate(base)
