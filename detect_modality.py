#!/usr/bin/env python3
"""
STEP 0 — deterministic modality detection. Classify each accession by STRUCTURED signals
(accession namespace, repository, gdstype/library_strategy, platform/instrument, panel/file
signatures), NOT by reading prose. Ambiguous/low-confidence -> quarantine, never guessed.

Output: results/modality_detected.csv
  accession, repository, platform_instrument, detected_modality, evidence_field, evidence_value, confidence

Template: GEO/SRA detection via E-utilities is wired; PRIDE/MassIVE/MetaboLights/Workbench
are classified by accession namespace (and should be confirmed via their own APIs before use).
"""
from __future__ import annotations
import csv, json, os, re, sys, time, urllib.parse, urllib.request

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
EMAIL = "you@example.org"

# accession namespace -> (repository, modality or 'QUERY')
NAMESPACE = [
    (re.compile(r"^PXD\d+$", re.I),       ("PRIDE/ProteomeXchange", "proteomics_ms")),
    (re.compile(r"^MSV\d+$", re.I),       ("MassIVE", "proteomics_ms")),
    (re.compile(r"^JPST\d+$", re.I),      ("jPOST", "proteomics_ms")),
    (re.compile(r"^MTBLS\d+$", re.I),     ("MetaboLights", "metabolomics")),   # lipidomics is a metabolomics subtype -> confirm
    (re.compile(r"^ST\d+$", re.I),        ("Metabolomics Workbench", "metabolomics")),
    (re.compile(r"^(GSE|GSM)\d+$", re.I), ("GEO", "QUERY")),
    (re.compile(r"^E-\w+-\d+$", re.I),    ("ArrayExpress/BioStudies", "QUERY")),
    (re.compile(r"^(SRR|SRX|SRP|PRJNA)\w+$", re.I), ("SRA", "QUERY")),
]

# keyword signatures over structured GEO fields (gdstype + platform title + summary)
SPATIAL   = ("visium", "slide-seq", "slideseq", "merfish", "xenium", "cosmx", "geomx",
             "spatial transcriptomic", "spatial gene expression", "stereo-seq")
SINGLECELL= ("single cell", "single-cell", "scrna", "snrna", "single nucleus", "single-nucleus",
             "10x chromium", "chromium", "smart-seq", "drop-seq", "cel-seq", "indrop")
RNASEQ    = ("expression profiling by high throughput sequencing", "rna-seq", "rna seq")
ARRAY     = ("expression profiling by array", "microarray", "in situ oligonucleotide")
AFFINITY  = ("olink", "somascan", "somalogic", "proximity extension", "aptamer")

def _get(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": f"detect-modality ({EMAIL})"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")

def geo_summary(acc: str) -> dict:
    ids = json.loads(_get(EUTILS + "esearch.fcgi?db=gds&retmode=json&term=" +
                          urllib.parse.quote(f"{acc}[ACCN]"))).get("esearchresult", {}).get("idlist", [])
    if not ids: return {}
    res = json.loads(_get(EUTILS + "esummary.fcgi?db=gds&retmode=json&id=" + ids[0])).get("result", {})
    time.sleep(0.34)
    return res.get(ids[0], {}) if ids[0] in res else {}

def classify_geo(rec: dict) -> tuple[str, str, str, str]:
    blob = " ".join(str(rec.get(k, "")) for k in ("gdstype", "title", "summary", "ptechtype", "taxon")).lower()
    plat = str(rec.get("ptechtype") or rec.get("gpl") or "")
    if any(k in blob for k in AFFINITY):   return "affinity_proteomics", "keywords", "affinity-proteomics signal", "medium"
    if any(k in blob for k in SPATIAL):     return "spatial", "platform/keywords", next(k for k in SPATIAL if k in blob), "high"
    if any(k in blob for k in SINGLECELL):  return "single_cell", "platform/keywords", next(k for k in SINGLECELL if k in blob), "high"
    if any(k in blob for k in ARRAY):       return "bulk_transcriptomics", "gdstype", "microarray", "high"
    if any(k in blob for k in RNASEQ):      return "bulk_transcriptomics", "gdstype", "rna-seq (bulk)", "medium"
    return "unknown", "gdstype", rec.get("gdstype", ""), "low"

def main(accessions: list[str]):
    rows = []
    for acc in accessions:
        repo, modality = "unknown", "unknown"
        field, value, conf = "namespace", acc, "low"
        plat = ""
        for rx, (r, m) in NAMESPACE:
            if rx.match(acc):
                repo = r
                if m == "QUERY" and repo.startswith(("GEO", "ArrayExpress", "SRA")):
                    rec = geo_summary(acc) if repo == "GEO" else {}
                    if rec:
                        modality, field, value, conf = classify_geo(rec)
                        plat = str(rec.get("ptechtype") or rec.get("gpl") or "")
                    else:
                        modality, field, value, conf = "unknown", "api", "no GEO summary -> confirm manually", "low"
                else:
                    modality, field, value, conf = m, "accession_namespace", repo, "high"
                break
        rows.append({"accession": acc, "repository": repo, "platform_instrument": plat,
                     "detected_modality": modality, "evidence_field": field,
                     "evidence_value": value, "confidence": conf})

    os.makedirs("results", exist_ok=True)
    cols = ["accession","repository","platform_instrument","detected_modality","evidence_field","evidence_value","confidence"]
    with open("results/modality_detected.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)

    quar = [r for r in rows if r["detected_modality"] == "unknown" or r["confidence"] == "low"]
    if quar:
        with open("results/quarantine.csv", "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(quar)
    print(f"classified {len(rows)} | quarantined (unknown/low-confidence) {len(quar)} -> results/modality_detected.csv")
    print(">>> For each modality, READ modalities/<modality>.md and apply its gates. Resolve quarantine before proceeding.")

if __name__ == "__main__":
    accs = sys.argv[1:]
    if not accs:
        print("usage: detect_modality.py ACC [ACC ...]  (e.g. GSE12345 PXD000001 MTBLS123)"); sys.exit(2)
    main(accs)
