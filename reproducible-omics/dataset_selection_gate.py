#!/usr/bin/env python3
"""
Dataset selection GATE (template) — decide GEO dataset inclusion by CODE against
structured metadata, never by an LLM reading abstracts.

Principle: organism and platform/assay are hard gates applied to structured fields.
Every accession gets an auditable INCLUDE/REJECT row naming the field+value that
triggered the decision. A human signs off `dataset_audit.csv` BEFORE any DE.

This is a template: adjust CONFIG, run in your pinned environment, review the audit.
Requires network access to NCBI E-utilities. No fabrication — if a field is missing,
the record is flagged for manual metadata retrieval, not guessed.
"""
from __future__ import annotations
import csv, json, sys, time, urllib.parse, urllib.request

# ----------------------------- CONFIG (edit, then pin) -----------------------------
CONFIG = {
    "allowed_organisms": {"Homo sapiens", "Mus musculus"},   # exact-match gate; dog/chicken/rat -> REJECT
    "required_assay": "rna-seq",                              # "rna-seq" or "microarray"
    "min_n_total": 6,                                         # reject tiny series (tune)
    "candidate_accessions": [                                 # OR build from an esearch query
        # "GSE205050", "GSE179285", ...
    ],
    "esearch_query": '',  # e.g. '(adipose[tiab]) AND "expression profiling by high throughput sequencing"[gdstype]'
    "email": "you@example.org",  # NCBI etiquette; set yours
    "outfile": "results/dataset_audit.csv",
}
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"

# RNA-seq vs microarray detection from GEO gdsType / platform technology strings
RNASEQ_MARKERS  = ("high throughput sequencing", "rna-seq", "rna seq", "sequencing")
ARRAY_MARKERS   = ("expression profiling by array", "microarray", "in situ oligonucleotide", "spotted")

def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": f"dataset-gate ({CONFIG['email']})"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def esearch_geo(query: str, retmax: int = 500) -> list[str]:
    """Return GEO DataSets UIDs for a query (structured gdstype filters recommended)."""
    if not query: return []
    url = EUTILS + "esearch.fcgi?db=gds&retmax=%d&retmode=json&term=%s" % (retmax, urllib.parse.quote(query))
    data = json.loads(_get(url))
    return data.get("esearchresult", {}).get("idlist", [])

def esummary_geo(uids: list[str]) -> list[dict]:
    """Fetch structured GEO summaries (organism, gdsType, platform, n_samples)."""
    out = []
    for i in range(0, len(uids), 100):
        chunk = ",".join(uids[i:i+100])
        url = EUTILS + "esummary.fcgi?db=gds&retmode=json&id=" + chunk
        res = json.loads(_get(url)).get("result", {})
        for uid in res.get("uids", []):
            out.append(res[uid])
        time.sleep(0.34)  # <= 3 req/s without API key
    return out

def detect_assay(gdstype: str, platform_tech: str) -> str:
    s = (gdstype + " " + platform_tech).lower()
    if any(m in s for m in RNASEQ_MARKERS): return "rna-seq"
    if any(m in s for m in ARRAY_MARKERS):  return "microarray"
    return "unknown"

def gate(rec: dict) -> tuple[str, str, str]:
    """Return (decision, trigger_field, trigger_value). Pure structured-field logic."""
    organism = (rec.get("taxon") or rec.get("organism") or "").strip()
    gdstype  = (rec.get("gdstype") or "")
    plat     = (rec.get("ptechtype") or rec.get("gpl") or "")
    n_total  = int(rec.get("n_samples") or 0)
    assay    = detect_assay(gdstype, plat)

    # ORGANISM GATE (exact membership; multi-organism strings split on ';')
    organisms = {o.strip() for o in organism.replace(",", ";").split(";") if o.strip()}
    if not organisms or not organisms.issubset(CONFIG["allowed_organisms"]):
        bad = organisms - CONFIG["allowed_organisms"]
        return "REJECT", "organism", organism or "MISSING -> manual retrieval (do not guess)"
    # ASSAY GATE
    if assay == "unknown":
        return "REJECT", "assay", f"undetectable from gdstype/platform -> manual check (gdstype='{gdstype}')"
    if assay != CONFIG["required_assay"]:
        return "REJECT", "assay", f"{assay} (required: {CONFIG['required_assay']})"
    # SIZE GATE
    if n_total < CONFIG["min_n_total"]:
        return "REJECT", "n_total", str(n_total)
    return "INCLUDE", "all_gates", f"organism={organism}; assay={assay}; n={n_total}"

def main():
    uids = esearch_geo(CONFIG["esearch_query"]) if CONFIG["esearch_query"] else []
    recs = esummary_geo(uids) if uids else []
    # also allow explicit accession list -> resolve to UIDs
    for acc in CONFIG["candidate_accessions"]:
        ids = esearch_geo(f"{acc}[ACCN]")
        recs += esummary_geo(ids)

    rows = []
    for rec in recs:
        acc = rec.get("accession", "?")
        decision, field, value = gate(rec)
        rows.append({
            "accession": acc,
            "organism_verbatim": rec.get("taxon") or rec.get("organism") or "",
            "platform_GPL": rec.get("gpl") or rec.get("ptechtype") or "",
            "gdstype": rec.get("gdstype") or "",
            "assay_detected": detect_assay(rec.get("gdstype",""), rec.get("ptechtype") or rec.get("gpl") or ""),
            "n_total": rec.get("n_samples") or "",
            "decision": decision,
            "trigger_field": field,
            "trigger_value": value,
        })

    import os; os.makedirs("results", exist_ok=True)
    with open(CONFIG["outfile"], "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else
                           ["accession","organism_verbatim","platform_GPL","gdstype","assay_detected","n_total","decision","trigger_field","trigger_value"])
        w.writeheader(); w.writerows(rows)

    inc = sum(r["decision"] == "INCLUDE" for r in rows)
    print(f"audited {len(rows)} | INCLUDE {inc} | REJECT {len(rows)-inc} -> {CONFIG['outfile']}")
    print(">>> STOP: a human must review and sign off results/dataset_audit.csv before any differential expression.")

if __name__ == "__main__":
    sys.exit(main())
