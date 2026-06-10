#!/usr/bin/env python3
"""verify.py — the terminal gate (SPEC.md section 8).

Implements all 15 verifier failure conditions. Reads EVERY text file with
encoding="utf-8". Emits an explicit `STATUS=PASS|NEEDS_REVIEW|BLOCKED` line, writes
results/run_status.json, and exits non-zero on any blocking violation.

Design: "fail loud if an artifact is present-but-wrong, and BLOCK if a required
artifact/threshold is missing." Modality-specific artifacts (cell QC, doublets) are
only demanded when that stage's artifacts exist OR a dataset of that modality is
INCLUDEd. This keeps Milestone-1 runs (selection + approval only) honest without
demanding stages that have not run.

Run from repo root:  python scripts/verify.py
Exit codes: 0 = PASS, 1 = BLOCKED, 3 = NEEDS_REVIEW, 2 = environment/setup error.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import sys
from pathlib import Path

# Repo root (where scripts/ + apps/ live) — used to locate the backend package.
REPO_ROOT = Path(__file__).resolve().parents[1]
# The workspace being verified. Defaults to the repo root, but per-project runs set
# OMICS_ROOT so the verifier reads that project's config.yaml + results/.
ROOT = Path(os.environ.get("OMICS_ROOT") or REPO_ROOT).resolve()
# Make the backend package importable for config validation (condition 2).
sys.path.insert(0, str(REPO_ROOT / "apps" / "backend"))

try:
    import yaml
except ImportError:
    print("STATUS=BLOCKED")
    print("BLOCKED: PyYAML not installed (use the pinned environment).", file=sys.stderr)
    sys.exit(2)


# --- result accumulation -------------------------------------------------------

CHECKS: list[tuple[bool, str, int]] = []  # (ok, message, condition_number)
REVIEW: list[str] = []


def check(ok: bool, msg: str, cond: int) -> None:
    CHECKS.append((bool(ok), msg, cond))


def needs_review(msg: str) -> None:
    REVIEW.append(msg)


def read_text_utf8(p: Path) -> str | None:
    """Read text as UTF-8. Returns None (and records a condition-1 failure) on decode error."""
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        check(False, f"[c1] not valid UTF-8: {p.relative_to(ROOT)}", 1)
        return None
    except FileNotFoundError:
        return None


def read_csv_rows(p: Path) -> list[dict[str, str]]:
    txt = read_text_utf8(p)
    if txt is None:
        return []
    return list(csv.DictReader(txt.splitlines()))


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    # Binary read by design: checksums hash raw bytes, not decoded text (SPEC 8 c1
    # UTF-8 requirement applies to text reads, handled by read_text_utf8).
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def emit_and_exit() -> None:
    fails = [(m, c) for ok, m, c in CHECKS if not ok]
    passes = [m for ok, m, c in CHECKS if ok]
    for m in passes:
        print(f"  PASS  {m}")
    for m, _ in fails:
        print(f"  FAIL  {m}")
    for m in REVIEW:
        print(f"  REVIEW {m}")
    print(f"\nverify: {len(passes)} PASS / {len(fails)} FAIL / {len(REVIEW)} review-flag")

    if fails:
        status = "BLOCKED"
        code = 1
    elif REVIEW:
        status = "NEEDS_REVIEW"
        code = 3
    else:
        status = "PASS"
        code = 0

    # Write run_status.json (UTF-8). Stdlib RunStatus shape mirrors models.RunStatus.
    from datetime import datetime, timezone
    run_status = {
        "status": status,
        "stage": "final_verifier",
        "checks_passed": len(passes),
        "checks_failed": len(fails),
        "details": [m for m, _ in fails] + [f"review: {m}" for m in REVIEW],
        "conditions_failed": sorted({c for _, c in fails}),
        "created_utc": datetime.now(timezone.utc).isoformat(),
    }
    out = ROOT / "results" / "run_status.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(run_status, indent=2), encoding="utf-8")

    print(f"STATUS={status}")
    sys.exit(code)


# --- condition 2: config present + schema-valid --------------------------------

cfg_path = ROOT / "config.yaml"
if not cfg_path.exists():
    check(False, "[c2] config.yaml missing", 2)
    emit_and_exit()

cfg_text = read_text_utf8(cfg_path)
if cfg_text is None:
    emit_and_exit()

cfg_raw = yaml.safe_load(cfg_text) or {}

# Prefer strict pydantic validation when the backend is importable.
try:
    from omics_backend.config_model import OmicsConfig  # type: ignore

    OmicsConfig.model_validate(cfg_raw)
    check(True, "[c2] config.yaml valid against schema", 2)
    _have_schema = True
except ImportError:
    check(True, "[c2] config.yaml loaded (pydantic backend unavailable; structural check only)", 2)
    _have_schema = False
except Exception as e:  # noqa: BLE001 - surface validation error verbatim
    check(False, f"[c2] config.yaml fails schema validation: {e}", 2)
    emit_and_exit()


# --- pull config values (structural fallbacks) ---------------------------------

proj = cfg_raw.get("project", {})
allowed = set(proj.get("allowed_organisms", []))
required_assay = str(proj.get("required_assay", "")).lower()
min_n = int(proj.get("min_n_total", 0) or 0)
qc = cfg_raw.get("qc", {})
template_mode = bool(qc.get("template_mode", False))
missing_cfg = cfg_raw.get("missingness", {})
sc_cfg = qc.get("single_cell", {})
paths = cfg_raw.get("paths", {})


def P(key: str, default: str) -> Path:
    return ROOT / str(paths.get(key, default))


dataset_audit_p = P("dataset_audit", "results/dataset_audit.csv")
modality_p = P("modality_detected", "results/modality_detected.csv")
approvals_dir = P("approvals_dir", "results/approvals")
checksums_p = P("checksums", "data/CHECKSUMS.txt")
results_dir = ROOT / "results"
de_dir = results_dir / "de"

# Import namespace check if available (condition 6).
try:
    from omics_backend.namespaces import is_well_formed  # type: ignore
except ImportError:
    import re

    _acc_re = re.compile(r"^(GSE|GSM|GPL|SRR|SRX|SRP|PRJNA|E-\w+-|PXD|MSV|JPST|MTBLS|ST)\w*$", re.I)

    def is_well_formed(a: str) -> bool:  # type: ignore
        return bool(_acc_re.match((a or "").strip()))


# --- condition 3: dataset_audit present + non-empty ----------------------------

if not dataset_audit_p.exists():
    check(False, f"[c3] dataset_audit missing: {dataset_audit_p.relative_to(ROOT)}", 3)
    audit_rows: list[dict[str, str]] = []
else:
    audit_rows = read_csv_rows(dataset_audit_p)
    if len(audit_rows) == 0 and not template_mode:
        check(False, "[c3] dataset_audit.csv has zero rows and qc.template_mode is false", 3)
    else:
        check(True, f"[c3] dataset_audit present ({len(audit_rows)} rows, template_mode={template_mode})", 3)

includes = [r for r in audit_rows if (r.get("decision", "").upper() == "INCLUDE")]

# --- condition 4: organism gate on INCLUDE rows --------------------------------

bad_org = []
for r in includes:
    org = r.get("organism_verbatim", "").strip()
    if not org or org not in allowed:
        bad_org.append(f"{r.get('accession', '?')}={org!r}")
check(not bad_org, "[c4] organism gate (INCLUDE in allowed_organisms)"
      + (f" -- VIOLATIONS: {bad_org}" if bad_org else ""), 4)

# --- condition 5: assay gate on INCLUDE rows -----------------------------------

if required_assay and required_assay != "any":
    bad_assay = [f"{r.get('accession', '?')}={r.get('assay_detected', '')}" for r in includes
                 if str(r.get("assay_detected", "")).lower() != required_assay]
    check(not bad_assay, f"[c5] assay gate (INCLUDE == {required_assay})"
          + (f" -- VIOLATIONS: {bad_assay}" if bad_assay else ""), 5)
else:
    check(True, "[c5] assay gate (required_assay=any -> skipped)", 5)

# --- condition 6: accession format valid for every row -------------------------

bad_acc = [r.get("accession", "") for r in audit_rows if not is_well_formed(r.get("accession", ""))]
check(not bad_acc, "[c6] accession IDs well-formed" + (f" -- MALFORMED: {bad_acc}" if bad_acc else ""), 6)

# --- condition 7: min n on INCLUDE rows ----------------------------------------

bad_n = []
for r in includes:
    raw = r.get("n_total")
    try:
        if int(float(raw)) < min_n:
            bad_n.append(f"{r.get('accession', '?')}={raw}")
    except (TypeError, ValueError):
        bad_n.append(f"{r.get('accession', '?')}=NaN")
check(not bad_n, f"[c7] min_n_total >= {min_n}" + (f" -- VIOLATIONS: {bad_n}" if bad_n else ""), 7)

# --- condition 8: INCLUDE datasets have confirmed modality ---------------------

modality_rows = read_csv_rows(modality_p) if modality_p.exists() else []
modmap = {r.get("accession", ""): r for r in modality_rows}
if includes:
    if not modality_p.exists():
        check(False, f"[c8] modality_detected.csv missing but INCLUDE rows exist", 8)
    else:
        missing_mod = []
        for r in includes:
            acc = r.get("accession", "")
            mr = modmap.get(acc)
            mod = (mr or {}).get("detected_modality", "")
            conf = (mr or {}).get("confidence", "")
            if not mr or mod in ("", "unknown") or conf == "low":
                missing_mod.append(f"{acc}={mod or 'absent'}/{conf or '-'}")
        check(not missing_mod, "[c8] INCLUDE datasets have confirmed modality"
              + (f" -- UNCONFIRMED: {missing_mod}" if missing_mod else ""), 8)
else:
    check(True, "[c8] modality confirmation (no INCLUDE rows yet)", 8)

# Which modalities are actually included (drives conditions 9, 10, 13).
included_modalities = {modmap.get(r.get("accession", ""), {}).get("detected_modality", "") for r in includes}


def _stage_ran(*relpaths: str) -> bool:
    return any((results_dir / rp).exists() for rp in relpaths)


# --- condition 9: bulk INCLUDE has sample-QC rows when sample QC ran -----------

sample_qc_p = results_dir / "sample_qc_audit.csv"
bulk_included = any(m in ("bulk_transcriptomics",) for m in included_modalities)
if sample_qc_p.exists():
    # SPEC c9 fires only when the sample-QC stage ran (artifact present) but is empty.
    sq_rows = read_csv_rows(sample_qc_p)
    if bulk_included and len(sq_rows) == 0:
        check(False, "[c9] sample_qc_audit.csv present but empty while bulk datasets INCLUDEd", 9)
    else:
        check(True, f"[c9] sample QC audit present ({len(sq_rows)} rows)", 9)
else:
    # Stage has not run yet: downstream gating is enforced by the DAG's approval
    # dependency, not by forcing a status here.
    check(True, "[c9] sample QC stage not run (gated by approval DAG)", 9)

# --- condition 10: single-cell QC + doublet integrity -------------------------

cell_qc_p = results_dir / "cell_qc_audit.csv"
doublet_p = results_dir / "doublet_audit.csv"
sc_included = any(m in ("single_cell",) for m in included_modalities)
if sc_included and cell_qc_p.exists():
    # Fires only when the cell-QC stage ran for single-cell data.
    cc = read_csv_rows(cell_qc_p)
    check(len(cc) > 0, "[c10] cell_qc_audit.csv has rows for single-cell datasets", 10)
# Doublet integrity: if doublets were removed, require tool/version/expected_rate/threshold + rows.
if doublet_p.exists():
    drows = read_csv_rows(doublet_p)
    removed = [r for r in drows if r.get("decision", "").upper() in ("EXCLUDE", "FLAG")]
    if removed:
        missing_fields = []
        for r in removed:
            for fld in ("tool", "tool_version", "expected_rate", "threshold"):
                if not str(r.get(fld, "")).strip():
                    missing_fields.append(f"{r.get('cell_id', '?')}:{fld}")
        check(not missing_fields, "[c10] doublet removals carry tool/version/expected_rate/threshold"
              + (f" -- MISSING: {missing_fields[:10]}" if missing_fields else ""), 10)
    else:
        check(True, f"[c10] doublet audit present ({len(drows)} rows, none removed)", 10)

# --- condition 11: missing-value handling specified; imputation has audit ------

zp = missing_cfg.get("zero_policy") or qc.get("bulk", {}).get("zero_policy")
nap = missing_cfg.get("not_applicable_policy") or qc.get("bulk", {}).get("not_applicable_policy")
na = missing_cfg.get("na_policy")
policies_ok = bool(zp) and bool(nap) and bool(na)
check(policies_ok, "[c11] missing-value policies set (zero/na/not_applicable)"
      + ("" if policies_ok else f" -- zero={zp!r} na={na!r} not_applicable={nap!r}"), 11)

imputation_enabled = bool(missing_cfg.get("imputation", {}).get("enabled", False))
imputation_audit_p = results_dir / "imputation_audit.csv"
if imputation_enabled or imputation_audit_p.exists():
    rows = read_csv_rows(imputation_audit_p) if imputation_audit_p.exists() else []
    check(imputation_audit_p.exists() and len(rows) > 0,
          "[c11] imputation used -> imputation_audit.csv present with rows", 11)

# --- condition 12: outlier exclusions carry an audit row -----------------------

outlier_p = results_dir / "outlier_audit.csv"
if outlier_p.exists():
    orows = read_csv_rows(outlier_p)
    excluded = [r for r in orows if r.get("decision", "").upper() == "EXCLUDE"]
    bad = []
    for r in excluded:
        for fld in ("metric_or_method", "value", "threshold", "reason"):
            if not str(r.get(fld, "")).strip():
                bad.append(f"{r.get('entity_id', '?')}:{fld}")
    check(not bad, "[c12] outlier exclusions carry metric/value/threshold/reason"
          + (f" -- MISSING: {bad[:10]}" if bad else ""), 12)

# --- condition 13: mito-fraction filtering needs gene-set + threshold ----------

mito_thr = sc_cfg.get("mitochondrial_fraction_threshold")
mito_def = sc_cfg.get("mitochondrial_gene_definition")
if sc_included and mito_thr is not None:
    # Mito filtering is configured -> it must carry a gene-set definition.
    check(bool(mito_def), "[c13] mito-fraction filtering has gene-set definition + threshold policy"
          + ("" if mito_def else " -- mitochondrial_gene_definition is null"), 13)

# --- condition 14: DE/integration gated on approval; methods match config ------

qc_approval_p = approvals_dir / "qc_approved.json"
de_present = de_dir.exists() and any(de_dir.glob("*_de.csv"))
integ_dir = results_dir / "integration"
integ_present = integ_dir.exists() and any(integ_dir.glob("*"))
if de_present or integ_present:
    if not qc_approval_p.exists():
        check(False, "[c14] DE/integration artifacts present but qc_approved.json approval missing", 14)
    else:
        check(True, "[c14] DE/integration gated by qc_approved.json", 14)
    # FDR genome-wide on DE method records
    fdr_bad = []
    for mk in de_dir.glob("*_method.json"):
        txt = read_text_utf8(mk)
        if txt is None:
            continue
        try:
            mj = json.loads(txt)
        except json.JSONDecodeError:
            fdr_bad.append(f"{mk.name}:unparseable")
            continue
        if str(mj.get("fdr_scope", "")).lower() != "genome_wide":
            fdr_bad.append(f"{mk.name}:fdr_scope={mj.get('fdr_scope')!r}")
    check(not fdr_bad, "[c14] DE FDR computed genome-wide" + (f" -- {fdr_bad}" if fdr_bad else ""), 14)

# --- condition 15: checksums present + match ----------------------------------

# Result-table checksums live in results/CHECKSUMS.txt once stage 19 runs; raw-input
# checksums live in data/CHECKSUMS.txt. Verify whichever exist; require at least one
# only if downstream (DE/integration) artifacts exist.
checksum_files = [checksums_p, results_dir / "CHECKSUMS.txt"]
present_cks = [c for c in checksum_files if c.exists()]
if de_present or integ_present:
    if not present_cks:
        check(False, "[c15] CHECKSUMS missing while DE/integration artifacts exist", 15)
for cks in present_cks:
    txt = read_text_utf8(cks)
    if txt is None:
        continue
    nbad = 0
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            digest, rel = line.split(None, 1)
        except ValueError:
            nbad += 1
            continue
        f = ROOT / rel.strip()
        if (not f.exists()) or sha256(f) != digest:
            nbad += 1
    check(nbad == 0, f"[c15] checksums match in {cks.relative_to(ROOT)}"
          + (f" -- {nbad} mismatch/missing" if nbad else ""), 15)

# --- quarantine -> NEEDS_REVIEW ------------------------------------------------

quarantine_p = P("quarantine", "results/quarantine.csv")
if quarantine_p.exists():
    qn = len(read_csv_rows(quarantine_p))
    if qn > 0:
        needs_review(f"{qn} quarantined accession(s) in {quarantine_p.relative_to(ROOT)}")

emit_and_exit()
