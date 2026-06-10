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
import re
import time
import urllib.parse
import urllib.request
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


# --- multi-project workspace + app-facing helpers ------------------------------

# Map common UI modality labels to a valid config required_assay (SPEC 5).
_ASSAY_ALIASES = {
    "bulk_transcriptomics": "rna-seq",
    "rna-seq": "rna-seq",
    "rnaseq": "rna-seq",
    "single_cell": "scrna-seq",
    "scrna-seq": "scrna-seq",
    "microarray": "microarray",
    "proteomics": "proteomics",
    "proteomics_ms": "proteomics",
    "metabolomics": "metabolomics",
    "any": "any",
}


def normalize_assay(value: Optional[str]) -> str:
    if not value:
        return "any"
    return _ASSAY_ALIASES.get(value.strip().lower(), "any")


def slug_id(name: str) -> str:
    """Stable, filesystem-safe project id from a name + short content hash."""
    base = re.sub(r"[^a-z0-9]+", "-", name.strip().lower()).strip("-") or "project"
    return f"{base[:32]}-{prov.sha256_text(name)[:6]}"


def project_dir(workspace: str | Path, project_id: str) -> Path:
    return Path(workspace) / "projects" / project_id


def create_project_from_inputs(
    name: str,
    workspace: str | Path,
    *,
    allowed_organisms: Optional[list[str]] = None,
    required_assay: Optional[str] = None,
    min_n_total: Optional[int] = None,
    seed: Optional[int] = None,
) -> Project:
    """Build a project under workspace/projects/<id> with a full, valid config.yaml
    assembled from defaults + the given overrides (SPEC 5)."""
    from .config_model import OmicsConfig, ProjectCfg  # local import to avoid cycle

    pid = slug_id(name)
    root = project_dir(workspace, pid)
    proj_cfg = ProjectCfg(
        id=pid,
        name=name,
        allowed_organisms=allowed_organisms or ["Homo sapiens", "Mus musculus"],
        required_assay=normalize_assay(required_assay),
        min_n_total=min_n_total if min_n_total is not None else 6,
        seed=seed if seed is not None else 1234,
    )
    full = OmicsConfig(project=proj_cfg)  # all other sections take SPEC defaults
    cfg_dict = full.model_dump(mode="json")
    return create_project(pid, name, root, base_config=cfg_dict)


def _acc_store(root: Path) -> Path:
    return root / "accessions.json"


def add_accessions(root: str | Path, accessions: list[str]) -> list[dict]:
    """Persist accessions (dedup, order-preserving) and return classified entries."""
    root = Path(root)
    store = _acc_store(root)
    existing = list_accessions(root)
    seen = {a for a in existing}
    merged = existing + [a for a in accessions if a not in seen and not seen.add(a)]
    store.write_text(json.dumps(merged, indent=2), encoding="utf-8")
    out = []
    for acc in merged:
        repo, _mod, valid = classify_namespace(acc)
        out.append({"id": acc, "repository": repo.value, "namespace_valid": valid})
    return out


def list_accessions(root: str | Path) -> list[str]:
    store = _acc_store(Path(root))
    if store.exists():
        data = json.loads(store.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    return []


# --- online metadata fetch (best-effort; falls back to offline namespace-only) --

_EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"


def _http_get(url: str, timeout: float = 8.0) -> Optional[str]:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "omics-desktop/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read().decode("utf-8", "replace")
    except Exception:  # noqa: BLE001 - network is best-effort; caller falls back
        return None


def fetch_metadata_online(accession: str) -> Optional[dict[str, str]]:
    """Best-effort structured-metadata fetch from NCBI E-utilities for GEO/SRA.

    Returns a dict of structured fields, or None on any failure (caller falls back to
    an offline namespace-only snapshot). Never raises.
    """
    repo, _mod, valid = classify_namespace(accession)
    if not valid:
        return None
    try:
        if repo.value == "GEO":
            sj = _http_get(_EUTILS + "esearch.fcgi?db=gds&retmode=json&term="
                           + urllib.parse.quote(f"{accession}[ACCN]"))
            if not sj:
                return None
            ids = json.loads(sj).get("esearchresult", {}).get("idlist", [])
            if not ids:
                return None
            time.sleep(0.34)
            rj = _http_get(_EUTILS + "esummary.fcgi?db=gds&retmode=json&id=" + ids[0])
            if not rj:
                return None
            rec = json.loads(rj).get("result", {}).get(ids[0], {})
            n = rec.get("n_samples")
            return {k: str(v) for k, v in {
                "organism": rec.get("taxon", ""),
                "gdstype": rec.get("gdstype", ""),
                "platform_GPL": rec.get("gpl", ""),
                "platform": rec.get("ptechtype", ""),
                "title": rec.get("title", ""),
                "n_total": n if n not in (None, "") else "",
            }.items() if v not in (None, "")}
        if repo.value == "SRA":
            sj = _http_get(_EUTILS + "esearch.fcgi?db=sra&retmode=json&term="
                           + urllib.parse.quote(accession))
            if not sj:
                return None
            ids = json.loads(sj).get("esearchresult", {}).get("idlist", [])
            if not ids:
                return None
            time.sleep(0.34)
            xj = _http_get(_EUTILS + "esummary.fcgi?db=sra&retmode=json&id=" + ids[0])
            if not xj:
                return None
            rec = json.loads(xj).get("result", {}).get(ids[0], {})
            expxml = rec.get("expxml", "")
            strat = ""
            m = re.search(r'<LIBRARY_STRATEGY>([^<]+)</LIBRARY_STRATEGY>', expxml)
            if m:
                strat = m.group(1)
            org = ""
            mo = re.search(r'ScientificName="([^"]+)"', expxml)
            if mo:
                org = mo.group(1)
            return {k: v for k, v in {
                "organism": org,
                "library_strategy": strat.lower(),
            }.items() if v}
    except Exception:  # noqa: BLE001
        return None
    return None


def fetch_project_metadata(root: str | Path, *, online: bool = True) -> list[dict]:
    """Fetch + store a snapshot for every stored accession. Returns client-shaped
    MetadataSnapshot dicts (accession, fetched_utc, source_api, raw_fields, checksum)."""
    root = Path(root)
    out = []
    for acc in list_accessions(root):
        injected = fetch_metadata_online(acc) if online else None
        source = "ncbi-eutils" if injected else "offline-namespace"
        snap = fetch_metadata(acc, root, injected=injected, source_api=source)
        out.append({
            "accession": snap.accession,
            "fetched_utc": snap.fetched_utc,
            "source_api": snap.source_api,
            "raw_fields": snap.fields,
            "checksum": snap.checksum or "",
        })
    return out


# --- QC dashboard aggregation --------------------------------------------------

def build_qc_dashboard(root: str | Path, project_id: str) -> dict:
    """Aggregate audit tables into the dashboard summary shape the UI expects."""
    root = Path(root)
    results = root / "results"

    def rows(name: str) -> list[dict]:
        p = results / name
        if not p.exists():
            return []
        return list(csv.DictReader(p.read_text(encoding="utf-8").splitlines()))

    audit = rows("dataset_audit.csv")
    included = sum(1 for r in audit if r.get("decision", "").upper() == "INCLUDE")
    rejected = sum(1 for r in audit if r.get("decision", "").upper() == "REJECT")
    quar = rows("quarantine.csv")

    modality_summary: dict[str, int] = {}
    for r in rows("modality_detected.csv"):
        m = r.get("detected_modality", "unknown") or "unknown"
        modality_summary[m] = modality_summary.get(m, 0) + 1

    sample_rows = rows("sample_qc_audit.csv")
    sample_summary = None
    if sample_rows:
        sample_summary = {
            "total": len(sample_rows),
            "passed": sum(1 for r in sample_rows if r.get("decision", "").upper() == "PASS"),
            "failed": sum(1 for r in sample_rows if r.get("decision", "").upper() in ("EXCLUDE", "FAIL")),
        }

    outlier_rows = rows("outlier_audit.csv")
    outlier_summary = None
    if outlier_rows:
        outlier_summary = {
            "total": len(outlier_rows),
            "candidate_only": sum(1 for r in outlier_rows if str(r.get("candidate_only", "")).lower() == "true"),
            "approved_exclusions": sum(1 for r in outlier_rows if str(r.get("approved", "")).lower() == "true"),
        }

    missing_rows = rows("missingness_audit.csv")
    missingness_summary = None
    if missing_rows:
        counts: dict[str, int] = {}
        for r in missing_rows:
            vc = r.get("value_class", "")
            if vc:
                counts[vc] = counts.get(vc, 0) + 1
        missingness_summary = {"value_class_counts": counts}

    return {
        "project_id": project_id,
        "dataset_audit_summary": {
            "total": len(audit), "included": included, "rejected": rejected,
            "quarantined": len(quar),
        },
        "sample_qc_summary": sample_summary,
        "outlier_summary": outlier_summary,
        "missingness_summary": missingness_summary,
        "modality_summary": modality_summary,
    }
