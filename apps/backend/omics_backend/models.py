"""Core Pydantic v2 models — SPEC.md section 6.

Every audit-row model carries append-only provenance where applicable
(reason / metric / value / threshold / approver / timestamp). Stdlib + pydantic only.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field

from .enums import (
    ApprovalDecision,
    Decision,
    Modality,
    QCDecision,
    Repository,
    Status,
    ValueClass,
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


# --- identity / metadata -------------------------------------------------------

class Project(_Frozen):
    id: str
    name: str
    created_utc: str = Field(default_factory=_utcnow)
    root_dir: str
    config_path: str = "config.yaml"
    config_hash: Optional[str] = None


class Accession(_Frozen):
    id: str
    repository: Repository = Repository.UNKNOWN
    namespace_valid: bool = False


class MetadataSnapshot(_Frozen):
    accession: str
    fetched_utc: str = Field(default_factory=_utcnow)
    source_api: str
    fields: dict[str, str] = Field(default_factory=dict)  # verbatim structured fields
    checksum: Optional[str] = None
    note: Optional[str] = None


# --- audit rows ----------------------------------------------------------------

class DatasetAuditRow(_Frozen):
    accession: str
    organism_verbatim: str = ""
    platform_GPL: str = ""
    gdstype: str = ""
    assay_detected: str = ""
    n_total: Optional[int] = None
    n_case: Optional[int] = None
    n_control: Optional[int] = None
    tissue: str = ""
    decision: Decision
    trigger_field: str = ""
    trigger_value: str = ""


class SampleQCRow(_Frozen):
    sample_id: str
    metric: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    decision: QCDecision
    reason: str = ""
    policy: str = ""


class FeatureQCRow(_Frozen):
    feature_id: str
    metric: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    value_class: ValueClass
    decision: QCDecision
    reason: str = ""


class CellQCRow(_Frozen):
    cell_id: str
    sample_id: str
    total_counts: Optional[float] = None
    detected_genes: Optional[int] = None
    mito_fraction: Optional[float] = None
    decision: QCDecision
    reason: str = ""


class DoubletAuditRow(_Frozen):
    cell_id: str
    sample_id: str
    tool: str
    tool_version: str
    expected_rate: Optional[float] = None
    score: Optional[float] = None
    threshold: Optional[float] = None
    decision: QCDecision
    reason: str = ""


class OutlierAuditRow(_Frozen):
    entity_id: str
    metric_or_method: str
    value: Optional[float] = None
    threshold: Optional[float] = None
    decision: QCDecision
    reason: str = ""
    candidate_only: bool = True
    approved: bool = False


class MissingnessAuditRow(_Frozen):
    entity_id: str
    value_class: ValueClass
    fraction: Optional[float] = None
    threshold: Optional[float] = None
    decision: QCDecision
    reason: str = ""


class ImputationAuditRow(_Frozen):
    target_matrix: str
    method: str
    version: str
    n_imputed: int = 0
    downweighted: bool = False
    reason: str = ""


# --- approvals / methods / status ----------------------------------------------

class ApprovalArtifact(_Frozen):
    artifact: str  # e.g. "dataset_audit_approved"
    approves: str  # path being approved, e.g. results/dataset_audit.csv
    approver: str
    approved_utc: str = Field(default_factory=_utcnow)
    config_hash: Optional[str] = None
    decision: ApprovalDecision = ApprovalDecision.APPROVED
    note: str = ""


class MethodRecord(_Frozen):
    stage: str
    tool: str = ""
    tool_version: str = ""
    package_versions: dict[str, str] = Field(default_factory=dict)
    params: dict[str, object] = Field(default_factory=dict)
    config_hash: Optional[str] = None
    random_seed: Optional[int] = None
    created_utc: str = Field(default_factory=_utcnow)
    # convenience policy mirrors (SPEC 3) where relevant
    zero_policy: Optional[str] = None
    na_policy: Optional[str] = None
    not_applicable_policy: Optional[str] = None
    fdr_scope: Optional[str] = None


class RunStatus(_Frozen):
    status: Status
    stage: str
    checks_passed: int = 0
    checks_failed: int = 0
    details: list[str] = Field(default_factory=list)
    conditions_failed: list[int] = Field(default_factory=list)
    created_utc: str = Field(default_factory=_utcnow)
