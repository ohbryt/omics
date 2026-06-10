"""config.yaml schema + validator — SPEC.md section 5.

config.yaml is the single source of truth for thresholds and policies. No threshold
may be hardcoded in any script. A `null` for a *required* threshold means BLOCKED at
verify time, never an invented value. This module validates *structure*; the verifier
enforces the runtime "required threshold is present" gates per modality.

CLI:  python -m omics_backend.config_model path/to/config.yaml
"""
from __future__ import annotations

import hashlib
import sys
from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- sections ------------------------------------------------------------------

class ProjectCfg(_Model):
    id: str
    name: str
    created_utc: Optional[str] = None
    allowed_organisms: list[str] = Field(min_length=1)
    required_assay: str
    min_n_total: int = Field(ge=0)
    seed: int = 1234

    @field_validator("required_assay")
    @classmethod
    def _assay(cls, v: str) -> str:
        allowed = {"rna-seq", "microarray", "scrna-seq", "proteomics", "metabolomics", "any"}
        if v.lower() not in allowed:
            raise ValueError(f"required_assay must be one of {sorted(allowed)}")
        return v.lower()


class AICfg(_Model):
    provider: str = "anthropic"
    model: str = "claude-opus-4-8"
    prompt_dir: str = "prompts"
    redaction: bool = True
    send_raw_data: bool = False  # never send raw seq/matrices/patient data unless True
    gateway_log: str = "logs/ai_prompts.jsonl"
    generated_code_manifest: str = "logs/generated_code_manifest.json"

    @field_validator("provider")
    @classmethod
    def _provider(cls, v: str) -> str:
        if v.lower() not in {"anthropic", "openai"}:
            raise ValueError("ai.provider must be 'anthropic' or 'openai'")
        return v.lower()


class OutlierCfg(_Model):
    methods: list[str] = Field(default_factory=lambda: ["mad", "pca_distance"])
    automatic_exclusion: bool = False


class BulkMissingnessCfg(_Model):
    max_sample_fraction: Optional[float] = None
    max_feature_fraction: Optional[float] = None


class ThresholdCfg(_Model):
    minimum: Optional[float] = None
    policy: Optional[str] = None
    covariate_allowed: bool = True


class BulkCfg(_Model):
    rin: ThresholdCfg = Field(default_factory=ThresholdCfg)
    mapping_rate: ThresholdCfg = Field(default_factory=ThresholdCfg)
    mito_fraction: ThresholdCfg = Field(default_factory=ThresholdCfg)
    library_size: ThresholdCfg = Field(default_factory=ThresholdCfg)
    missingness: BulkMissingnessCfg = Field(default_factory=BulkMissingnessCfg)
    zero_policy: str = "distinguish_biological_zero_from_missing"
    not_applicable_policy: str = "do_not_convert_to_zero"
    outlier: OutlierCfg = Field(default_factory=OutlierCfg)


class DoubletCfg(_Model):
    tool: Optional[str] = None
    version: Optional[str] = None
    expected_rate: Optional[float] = None
    threshold: Optional[float] = None
    consensus_required: bool = False


class AmbientRNACfg(_Model):
    method: Optional[str] = None


class SingleCellCfg(_Model):
    cell_qc_metrics: list[str] = Field(
        default_factory=lambda: ["total_counts", "detected_genes", "mitochondrial_fraction"]
    )
    threshold_policy: str = "data_driven_documented"
    mitochondrial_gene_definition: Optional[str] = None
    mitochondrial_fraction_threshold: Optional[float] = None
    doublet: DoubletCfg = Field(default_factory=DoubletCfg)
    ambient_rna: AmbientRNACfg = Field(default_factory=AmbientRNACfg)
    de_method: str = "pseudobulk_by_donor"


class QCCfg(_Model):
    template_mode: bool = False
    require_human_approval_after_dataset_audit: bool = True
    bulk: BulkCfg = Field(default_factory=BulkCfg)
    single_cell: SingleCellCfg = Field(default_factory=SingleCellCfg)


class ImputationCfg(_Model):
    enabled: bool = False
    method: Optional[str] = None
    version: Optional[str] = None
    target_matrix: Optional[str] = None
    downweight: bool = False


class MissingnessCfg(_Model):
    max_sample_fraction: Optional[float] = None
    max_feature_fraction: Optional[float] = None
    below_lod_policy: Optional[str] = None
    zero_policy: str = "distinguish_biological_zero_from_missing"
    na_policy: str = "treat_as_true_missing_unless_specified"
    not_applicable_policy: str = "do_not_convert_to_zero"
    imputation: ImputationCfg = Field(default_factory=ImputationCfg)


class IntegrationCfg(_Model):
    method: Optional[str] = None  # combat | combat_seq | harmony | seurat | mofa2
    require_layers_qc_passed: bool = True

    @field_validator("method")
    @classmethod
    def _method(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        allowed = {"combat", "combat_seq", "harmony", "seurat", "mofa2"}
        if v.lower() not in allowed:
            raise ValueError(f"integration.method must be one of {sorted(allowed)} or null")
        return v.lower()


class FDRCfg(_Model):
    method: str = "BH"
    scope: str = "genome_wide"
    threshold: float = 0.05

    @field_validator("scope")
    @classmethod
    def _scope(cls, v: str) -> str:
        if v != "genome_wide":
            raise ValueError("fdr.scope must be 'genome_wide' (SPEC 8 cond. 14)")
        return v


class VerifierCfg(_Model):
    strict: bool = True
    fail_on_empty_audit: bool = True
    required_artifacts: list[str] = Field(default_factory=list)


class PathsCfg(_Model):
    model_config = ConfigDict(extra="allow")  # path map; allow extra named paths
    dataset_audit: str = "results/dataset_audit.csv"
    modality_detected: str = "results/modality_detected.csv"
    quarantine: str = "results/quarantine.csv"
    approvals_dir: str = "results/approvals"
    run_status: str = "results/run_status.json"
    checksums: str = "data/CHECKSUMS.txt"
    run_config_used: str = "results/run_config_used.json"


class OmicsConfig(_Model):
    """Top-level config.yaml model (SPEC 5)."""

    project: ProjectCfg
    ai: AICfg = Field(default_factory=AICfg)
    qc: QCCfg = Field(default_factory=QCCfg)
    missingness: MissingnessCfg = Field(default_factory=MissingnessCfg)
    integration: IntegrationCfg = Field(default_factory=IntegrationCfg)
    fdr: FDRCfg = Field(default_factory=FDRCfg)
    verifier: VerifierCfg = Field(default_factory=VerifierCfg)
    paths: PathsCfg = Field(default_factory=PathsCfg)


# --- helpers -------------------------------------------------------------------

def load_config(path: str | Path) -> OmicsConfig:
    """Load + validate a config.yaml. Raises pydantic.ValidationError on bad config."""
    text = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(text) or {}
    return OmicsConfig.model_validate(data)


def config_hash(path: str | Path) -> str:
    """Stable sha256 of the raw config bytes (for provenance)."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def export_json_schema() -> dict:
    return OmicsConfig.model_json_schema()


def _main(argv: list[str]) -> int:
    if not argv:
        print("usage: python -m omics_backend.config_model CONFIG.yaml", file=sys.stderr)
        return 2
    try:
        cfg = load_config(argv[0])
    except FileNotFoundError:
        print(f"BLOCKED: config not found: {argv[0]}", file=sys.stderr)
        return 2
    except Exception as e:  # noqa: BLE001 - surface validation error verbatim
        print(f"BLOCKED: config invalid: {e}", file=sys.stderr)
        return 1
    print(f"PASS: config valid (project.id={cfg.project.id}, hash={config_hash(argv[0])[:12]})")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
