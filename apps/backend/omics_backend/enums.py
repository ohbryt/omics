"""Shared enums — SPEC.md sections 1.2, 3, 4. Stdlib only."""
from __future__ import annotations

from enum import Enum


class Status(str, Enum):
    """Terminal run status (SPEC 1.2). Always exactly one of these."""

    PASS = "PASS"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    BLOCKED = "BLOCKED"


class Decision(str, Enum):
    INCLUDE = "INCLUDE"
    REJECT = "REJECT"


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class QCDecision(str, Enum):
    PASS = "PASS"
    FLAG = "FLAG"
    EXCLUDE = "EXCLUDE"
    CANDIDATE = "CANDIDATE"


class ValueClass(str, Enum):
    """Missing-value taxonomy (SPEC 3). Never collapse these."""

    BIOLOGICAL_ZERO = "biological_zero"
    TECHNICAL_ZERO = "technical_zero"
    BELOW_LOD = "below_lod"
    TRUE_MISSING = "true_missing"
    UNAVAILABLE_METADATA = "unavailable_metadata"
    IMPUTED_PLACEHOLDER = "imputed_placeholder"
    NOT_APPLICABLE = "not_applicable"


class Modality(str, Enum):
    BULK_TRANSCRIPTOMICS = "bulk_transcriptomics"
    SINGLE_CELL = "single_cell"
    SPATIAL = "spatial"
    PROTEOMICS_MS = "proteomics_ms"
    AFFINITY_PROTEOMICS = "affinity_proteomics"
    METABOLOMICS = "metabolomics"
    LIPIDOMICS = "lipidomics"
    UNKNOWN = "unknown"


class Repository(str, Enum):
    GEO = "GEO"
    SRA = "SRA"
    ARRAYEXPRESS = "ArrayExpress/BioStudies"
    PRIDE = "PRIDE/ProteomeXchange"
    MASSIVE = "MassIVE"
    JPOST = "jPOST"
    METABOLIGHTS = "MetaboLights"
    METABOLOMICS_WORKBENCH = "Metabolomics Workbench"
    UNKNOWN = "unknown"
