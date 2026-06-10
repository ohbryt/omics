#!/usr/bin/env python3
"""
verify.py - terminal gate. Universal assertions PLUS modality-specific dispatch.

Universal: organism gate, ID format, env pinned, run-config match, checksums.
Per modality (from results/modality_detected.csv): assert each included dataset's method record
(results/method/<acc>.json or results/de/<acc>_method.json) contains the required, correctly-valued
keys for its modality. Exits non-zero on ANY violation. Emits STATUS (PASS/BLOCKED/NEEDS_REVIEW).
Stdlib + PyYAML.
"""
from __future__ import annotations
import csv, hashlib, json, re, sys
from pathlib import Path
try:
    import yaml
except ImportError:
    print("BLOCKED: PyYAML not installed (use the pinned environment)."); sys.exit(2)

ROOT = Path(__file__).resolve().parents[1]
CHECKS: list[tuple[bool,str]] = []
def check(ok, msg): CHECKS.append((bool(ok), msg))
def sha256(p: Path):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for b in iter(lambda: f.read(1<<20), b""): h.update(b)
    return h.hexdigest()

# ---------- modality requirements (presence-keys; (key,expected-substring) value-checks) ----------
MOD_REQUIRED = {
 "bulk_transcriptomics": ["fdr_scope","normalization"],
 "single_cell":          ["seed","integration_tool","integration_version","annotation_reference","de_method","qc_thresholds"],
 "spatial":              ["platform_class","feature_space","seed"],   # + segmentation_tool OR deconvolution_tool (checked below)
 "proteomics_ms":        ["search_engine","search_engine_version","fasta_version","fdr_type","imputation_method","normalization","acquisition"],
 "affinity_proteomics":  ["platform","panel_version","units","lod_handling"],
 "metabolomics":         ["tool","tool_version","drift_correction","id_confidence_level","ion_mode"],
 "lipidomics":           ["tool","tool_version","id_confidence_level","shorthand_level","internal_standards","isomer_handling"],
}
MOD_VALUES = {
 "bulk_transcriptomics": [("fdr_scope","genome_wide")],
 "single_cell":          [("de_method","pseudobulk")],
 "proteomics_ms":        [("fdr_type","target_decoy")],
}
def method_record(acc: str):
    for cand in (ROOT/f"results/method/{acc}.json", ROOT/f"results/de/{acc}_method.json"):
        if cand.exists():
            try: return json.loads(cand.read_text())
            except Exception: return {}
    return None

# ---------- load config ----------
cfg_path = ROOT/"config.yaml"
if not cfg_path.exists(): print("BLOCKED: config.yaml missing"); sys.exit(2)
cfg = yaml.safe_load(cfg_path.read_text())
allowed = set(cfg["allowed_organisms"]); P = {k: ROOT/v for k,v in cfg["paths"].items()}
ACC_RE = re.compile(r"^(GSE|GSM|GPL|SRR|SRX|SRP|PRJNA|E-\w+-\d+|PXD|MSV|JPST|MTBLS|ST)\w*$", re.I)

# ---------- universal ----------
audit = P["dataset_audit"]
rows = list(csv.DictReader(open(audit, newline=""))) if audit.exists() else []
check(audit.exists(), f"dataset_audit present ({len(rows)} rows)")
includes = [r for r in rows if r.get("decision","").upper()=="INCLUDE"]

bad_org=[f"{r.get('accession','?')}={r.get('organism_verbatim','')!r}" for r in includes
         if not {t.strip() for t in re.split(r'[;,]', r.get('organism_verbatim','')) if t.strip()}.issubset(allowed)
         or not r.get('organism_verbatim','').strip()]
check(not bad_org, "organism gate (all INCLUDE in allowed_organisms)"+(f" -- {bad_org}" if bad_org else ""))

bad_acc=[r.get("accession","") for r in rows if not ACC_RE.match(r.get("accession","") or "")]
check(not bad_acc, "accession IDs well-formed"+(f" -- {bad_acc}" if bad_acc else ""))

env=P["env_lock"]; check(env.exists() and env.stat().st_size>0, "env.lock present & non-empty")
ruc=P["run_config_used"]
if ruc.exists():
    used=json.loads(ruc.read_text())
    for k in ("required_assay","fdr_scope","probe_collapse_rule"):
        check(str(used.get(k,"")).lower()==str(cfg.get(k,"")).lower(), f"run_config_used.{k} matches config")
else:
    check(False, "run_config_used.json missing")

cks=P["checksums"]
if cks.exists():
    nbad=0
    for line in cks.read_text().splitlines():
        line=line.strip()
        if not line or line.startswith("#"): continue
        try: digest, rel = line.split(None,1)
        except ValueError: nbad+=1; continue
        f=ROOT/rel.strip()
        if (not f.exists()) or sha256(f)!=digest: nbad+=1
    check(nbad==0, "committed checksums match"+(f" -- {nbad} bad" if nbad else ""))
else:
    check(False, "CHECKSUMS.txt missing")

# ---------- modality dispatch ----------
mod_csv = ROOT/"results/modality_detected.csv"
mod_of = {}
if mod_csv.exists():
    for r in csv.DictReader(open(mod_csv, newline="")):
        mod_of[r["accession"]] = r["detected_modality"]
    check(True, f"modality_detected present ({len(mod_of)} accessions)")
else:
    check(False, "modality_detected.csv missing (run detect_modality.py first)")

for r in includes:
    acc = r.get("accession","?"); mod = mod_of.get(acc, "UNDETECTED")
    if mod in ("UNDETECTED","unknown",""):
        check(False, f"{acc}: modality not detected/confirmed"); continue
    rec = method_record(acc)
    if rec is None:
        check(False, f"{acc} [{mod}]: method record missing (results/method/{acc}.json)"); continue
    for key in MOD_REQUIRED.get(mod, []):
        check(key in rec and str(rec[key]).strip()!="", f"{acc} [{mod}]: method record has '{key}'")
    for key, expect in MOD_VALUES.get(mod, []):
        check(expect.lower() in str(rec.get(key,"")).lower(), f"{acc} [{mod}]: {key} ~ '{expect}'")
    if mod == "spatial":
        check(any(k in rec for k in ("segmentation_tool","deconvolution_tool")),
              f"{acc} [spatial]: segmentation_tool or deconvolution_tool recorded")

# ---------- report ----------
q = P["quarantine"]; n_quar = (sum(1 for _ in csv.DictReader(open(q, newline=""))) if q.exists() else 0)
fails=[m for ok,m in CHECKS if not ok]; passes=[m for ok,m in CHECKS if ok]
print("\n".join(f"  PASS  {m}" for m in passes))
for m in fails: print(f"  FAIL  {m}")
print(f"\nverify: {len(passes)} PASS / {len(fails)} FAIL | quarantined: {n_quar}")
if fails: print("STATUS=BLOCKED"); sys.exit(1)
if n_quar>0: print("STATUS=NEEDS_REVIEW"); sys.exit(3)
print("STATUS=PASS"); sys.exit(0)
