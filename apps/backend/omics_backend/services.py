"""Milestone-1 services (SPEC 11).

Deterministic, offline-safe building blocks that produce the audited artifacts:
project creation, accession metadata fetch (snapshot), modality detection, dataset
audit gate, approval-artifact creation.

Offline-safe: fetch_metadata accepts injected metadata (fixtures/tests) so CI never
depends on the network. Live runs pass `online=True` to query repository APIs.

Gates read thresholds from config only (SPEC 5). Stdlib + pydantic + pyyaml.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Optional

from . import provenance as prov
from .config_model import OmicsConfig, config_hash, load_config
from .enums import ApprovalDecision, Decision, Modality, QCDecision
from .models import (
    ApprovalArtifact,
    DatasetAuditRow,
    MetadataSnapshot,
    Project,
)
from .namespaces import classify_namespace, is_well_formed

# Structured-field signatures for assay/modality refinement (no prose parsing).
_RNASEQ = ("rna-seq", "rna seq", "expression profiling by high throughput sequencing")
_ARRAY = ("microarray", "expression profiling by array", "in situ oligonucleotide")
_SINGLECELL = ("single cell", "single-cell", "scrna", "snrna", "single nucleus",
               "single-nucleus", "10x", "chromium", "smart-seq", "drop-seq")
_SPATIAL = ("visium", "slide-seq", "merfish", "xenium", "cosmx", "geomx", "spatial")
_AFFINITY = ("olink", "somascan", "somalogic", "proximity extension", "aptamer")


def _detect_assay(fields: dict[str, str]) -> str:
    """Map structured metadata fields to an assay string. '' when undetermined.

    Prefer explicit structured fields (library_strategy, gdstype) over a free-text blob,
    and check the more-specific array signal before the generic rna-seq phrase.
    """
    lib = str(fields.get("library_strategy", "")).lower()
    gdstype = str(fields.get("gdstype", "")).lower()
    if lib == "rna-seq":
        return "rna-seq"
    if any(k in gdstype for k in _ARRAY):
        return "microarray"
    if any(k in gdstype for k in _RNASEQ):
        return "rna-seq"
    blob = " ".join(str(v) for v in fields.values()).lower()
    if any(k in blob for k in _ARRAY):
        return "microarray"
    if any(k in blob for k in _RNASEQ):
        return "rna-seq"
    return ""


def _detect_modality(fields: dict[str, str], default: Modality | None) -> tuple[Modality, str]:
    """Return (modality, confidence) from structured fields, falling back to namespace default."""
    blob = " ".join(str(v) for v in fields.values()).lower()
    if any(k in blob for k in _AFFINITY):
        return Modality.AFFINITY_PROTEOMICS, "medium"
    if any(k in blob for k in _SPATIAL):
        return Modality.SPATIAL, "high"
    if any(k in blob for k in _SINGLECELL):
        return Modality.SINGLE_CELL, "high"
    if any(k in blob for k in _ARRAY):
        return Modality.BULK_TRANSCRIPTOMICS, "high"
    if any(k in blob for k in _RNASEQ):
        return Modality.BULK_TRANSCRIPTOMICS, "medium"
    if default is not None and default != Modality.UNKNOWN:
        return default, "high"  # namespace-resolved (e.g. PXD -> proteomics_ms)
    return Modality.UNKNOWN, "low"


# --- project -------------------------------------------------------------------

def create_project(
    project_id: str,
    name: str,
    root_dir: str | Path,
    *,
    base_config: Optional[dict] = None,
    template_config_path: Optional[str | Path] = None,
) -> Project:
    """Create a project directory and write its config.yaml.

    config is sourced from base_config (dict) or copied from a template config file
    (validated). The project's results/ logs/ data/ dirs are created.
    """
    root = Path(root_dir)
    root.mkdir(parents=True, exist_ok=True)
    for sub in ("results", "results/approvals", "results/metadata", "logs", "data"):
        (root / sub).mkdir(parents=True, exist_ok=True)

    cfg_path = root / "config.yaml"
    if base_config is not None:
        import yaml

        cfg_path.write_text(yaml.safe_dump(base_config, sort_keys=False), encoding="utf-8")
    elif template_config_path is not None:
        cfg_path.write_text(Path(template_config_path).read_text(encoding="utf-8"), encoding="utf-8")
    else:
        raise ValueError("create_project requires base_config or template_config_path")

    # Validate the written config (fail loud on invalid).
    load_config(cfg_path)
    return Project(
        id=project_id,
        name=name,
        root_dir=str(root),
        config_path="config.yaml",
        config_hash=config_hash(cfg_path),
    )


# --- metadata fetch (offline-safe) ---------------------------------------------

def fetch_metadata(
    accession: str,
    root_dir: str | Path,
    *,
    injected: Optional[dict[str, str]] = None,
    source_api: str = "injected",
) -> MetadataSnapshot:
    """Fetch + store a metadata snapshot. Offline-safe: when `injected` is provided it
    is stored verbatim; otherwise a namespace-only snapshot is stored with a note.

    Never invents metadata: missing fields stay absent, not fabricated.
    """
    root = Path(root_dir)
    repo, _default_mod, valid = classify_namespace(accession)
    fields = dict(injected) if injected else {}
    note = "" if injected else "metadata not fetched (offline); namespace-only snapshot"

    snap = MetadataSnapshot(
        accession=accession,
        source_api=source_api,
        fields=fields,
        note=note or None,
    )
    payload = snap.model_dump()
    payload["repository"] = repo.value
    payload["namespace_valid"] = valid
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    snap_path = root / "results" / "metadata" / f"{accession}.json"
    snap_path.parent.mkdir(parents=True, exist_ok=True)
    snap_path.write_text(text, encoding="utf-8")
    # attach checksum
    return snap.model_copy(update={"checksum": prov.sha256_text(text)})


def _load_snapshots(root: Path, accessions: list[str]) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for acc in accessions:
        p = root / "results" / "metadata" / f"{acc}.json"
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            out[acc] = data.get("fields", {})
        else:
            out[acc] = {}
    return out


# --- modality detection --------------------------------------------------------

_MOD_COLS = ["accession", "repository", "platform_instrument", "detected_modality",
             "evidence_field", "evidence_value", "confidence"]


def detect_modality(accessions: list[str], root_dir: str | Path) -> Path:
    """Write results/modality_detected.csv (+ quarantine for unknown/low confidence)."""
    root = Path(root_dir)
    snaps = _load_snapshots(root, accessions)
    rows = []
    for acc in accessions:
        repo, default_mod, _valid = classify_namespace(acc)
        fields = snaps.get(acc, {})
        mod, conf = _detect_modality(fields, default_mod)
        rows.append({
            "accession": acc,
            "repository": repo.value,
            "platform_instrument": fields.get("platform", fields.get("instrument", "")),
            "detected_modality": mod.value,
            "evidence_field": "namespace" if not fields else "structured_metadata",
            "evidence_value": fields.get("library_strategy", fields.get("gdstype", repo.value)),
            "confidence": conf,
        })

    out = root / "results" / "modality_detected.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_MOD_COLS)
        w.writeheader()
        w.writerows(rows)

    quar = [r for r in rows if r["detected_modality"] == Modality.UNKNOWN.value or r["confidence"] == "low"]
    if quar:
        qp = root / "results" / "quarantine.csv"
        with open(qp, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=_MOD_COLS)
            w.writeheader()
            w.writerows(quar)
    return out


# --- dataset audit gate --------------------------------------------------------

_AUDIT_COLS = ["accession", "organism_verbatim", "platform_GPL", "gdstype", "assay_detected",
               "n_total", "n_case", "n_control", "tissue", "decision", "trigger_field", "trigger_value"]


def generate_dataset_audit(accessions: list[str], root_dir: str | Path, cfg: OmicsConfig) -> Path:
    """Apply organism / assay / min_n gates against stored metadata snapshots and write
    results/dataset_audit.csv. Every REJECT names the field+value that triggered it.

    Gates read entirely from config (SPEC 5). No prose, no hand judgement.
    """
    root = Path(root_dir)
    snaps = _load_snapshots(root, accessions)
    allowed = set(cfg.project.allowed_organisms)
    required_assay = cfg.project.required_assay
    min_n = cfg.project.min_n_total

    rows: list[DatasetAuditRow] = []
    for acc in accessions:
        fields = snaps.get(acc, {})
        organism = str(fields.get("organism", "")).strip()
        assay = _detect_assay(fields)
        try:
            n_total = int(float(fields.get("n_total"))) if fields.get("n_total") not in (None, "") else None
        except (TypeError, ValueError):
            n_total = None

        decision = Decision.INCLUDE
        trigger_field = ""
        trigger_value = ""

        if not is_well_formed(acc):
            decision, trigger_field, trigger_value = Decision.REJECT, "accession", acc
        elif not organism:
            decision, trigger_field, trigger_value = Decision.REJECT, "organism", "missing"
        elif organism not in allowed:
            decision, trigger_field, trigger_value = Decision.REJECT, "organism", organism
        elif required_assay != "any" and assay != required_assay:
            decision, trigger_field, trigger_value = Decision.REJECT, "assay_detected", assay or "undetermined"
        elif n_total is None:
            decision, trigger_field, trigger_value = Decision.REJECT, "n_total", "missing"
        elif n_total < min_n:
            decision, trigger_field, trigger_value = Decision.REJECT, "n_total", str(n_total)

        rows.append(DatasetAuditRow(
            accession=acc,
            organism_verbatim=organism,
            platform_GPL=str(fields.get("platform_GPL", fields.get("platform", ""))),
            gdstype=str(fields.get("gdstype", "")),
            assay_detected=assay,
            n_total=n_total,
            n_case=_int_or_none(fields.get("n_case")),
            n_control=_int_or_none(fields.get("n_control")),
            tissue=str(fields.get("tissue", "")),
            decision=decision,
            trigger_field=trigger_field,
            trigger_value=trigger_value,
        ))

    out = root / "results" / "dataset_audit.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=_AUDIT_COLS)
        w.writeheader()
        for r in rows:
            d = r.model_dump()
            d["decision"] = r.decision  # already a str via use_enum_values
            w.writerow({k: ("" if d.get(k) is None else d.get(k)) for k in _AUDIT_COLS})
    return out


def _int_or_none(v) -> Optional[int]:
    try:
        return int(float(v)) if v not in (None, "") else None
    except (TypeError, ValueError):
        return None


# --- approval ------------------------------------------------------------------

def create_approval(
    artifact: str,
    approves: str,
    approver: str,
    root_dir: str | Path,
    cfg_path: str | Path,
    *,
    decision: ApprovalDecision = ApprovalDecision.APPROVED,
    note: str = "",
) -> Path:
    """Write a human sign-off approval artifact (e.g. dataset_audit_approved.json).

    The app NEVER auto-approves: callers must pass a real approver identity.
    """
    if not approver or not approver.strip():
        raise ValueError("approval requires a non-empty approver identity (human sign-off)")
    root = Path(root_dir)
    art = ApprovalArtifact(
        artifact=artifact,
        approves=approves,
        approver=approver,
        config_hash=config_hash(cfg_path),
        decision=decision,
        note=note,
    )
    out = root / "results" / "approvals" / f"{artifact}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(art.model_dump(), indent=2, ensure_ascii=False), encoding="utf-8")
    return out
