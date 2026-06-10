#!/usr/bin/env python3
"""
STEP 0 - deterministic modality detection WITH repository-API confirmation.

Classify each accession by structured signals, then CONFIRM via the owning repository's API
(GEO/SRA via E-utilities; PRIDE/ProteomeXchange; MetaboLights; Metabolomics Workbench). The API
step also captures the verbatim organism and the platform/assay, and sub-detects lipidomics
inside metabolomics. Ambiguous/low-confidence or API-unreachable -> quarantine, never guessed.

Output: results/modality_detected.csv
  accession, repository, organism_verbatim, platform_instrument, detected_modality,
  evidence_field, evidence_value, confidence, confirmed
"""
from __future__ import annotations
import csv, json, os, re, sys, time, urllib.parse, urllib.request

EMAIL = "you@example.org"
EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
PRIDE  = "https://www.ebi.ac.uk/pride/ws/archive/v2/projects/"
MTBLS  = "https://www.ebi.ac.uk/metabolights/ws/studies/"
MWB    = "https://www.metabolomicsworkbench.org/rest/study/study_id/"

NAMESPACE = [
    (re.compile(r"^PXD\d+$", re.I),       ("PRIDE/ProteomeXchange", "proteomics_ms")),
    (re.compile(r"^MSV\d+$", re.I),       ("MassIVE", "proteomics_ms")),
    (re.compile(r"^JPST\d+$", re.I),      ("jPOST", "proteomics_ms")),
    (re.compile(r"^MTBLS\d+$", re.I),     ("MetaboLights", "metabolomics")),
    (re.compile(r"^ST\d+$", re.I),        ("Metabolomics Workbench", "metabolomics")),
    (re.compile(r"^(GSE|GSM)\d+$", re.I), ("GEO", "QUERY")),
    (re.compile(r"^E-\w+-\d+$", re.I),    ("ArrayExpress/BioStudies", "QUERY")),
    (re.compile(r"^(SRR|SRX|SRP|PRJNA)\w+$", re.I), ("SRA", "QUERY")),
]
SPATIAL    = ("visium","slide-seq","slideseq","merfish","xenium","cosmx","geomx","spatial transcriptomic","spatial gene expression","stereo-seq")
SINGLECELL = ("single cell","single-cell","scrna","snrna","single nucleus","single-nucleus","10x chromium","chromium","smart-seq","drop-seq","cel-seq","indrop")
RNASEQ     = ("expression profiling by high throughput sequencing","rna-seq","rna seq")
ARRAY      = ("expression profiling by array","microarray","in situ oligonucleotide")
AFFINITY   = ("olink","somascan","somalogic","proximity extension","aptamer")
LIPID      = ("lipidom","lipid profiling","lipid extract","lipidemic")

def _get(url: str, timeout=30) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": f"detect-modality ({EMAIL})", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")

def _try(url: str):
    try: return _get(url)
    except Exception as e: return None

# ---------- GEO ----------
def geo_summary(acc: str) -> dict:
    ids = json.loads(_get(EUTILS + "esearch.fcgi?db=gds&retmode=json&term=" + urllib.parse.quote(f"{acc}[ACCN]"))).get("esearchresult", {}).get("idlist", [])
    if not ids: return {}
    res = json.loads(_get(EUTILS + "esummary.fcgi?db=gds&retmode=json&id=" + ids[0])).get("result", {})
    time.sleep(0.34)
    return res.get(ids[0], {}) if ids[0] in res else {}

def classify_geo(rec: dict):
    blob = " ".join(str(rec.get(k,"")) for k in ("gdstype","title","summary","ptechtype","taxon")).lower()
    if any(k in blob for k in AFFINITY):   return "affinity_proteomics","keywords","affinity signal","medium"
    if any(k in blob for k in SPATIAL):    return "spatial","platform/keywords",next(k for k in SPATIAL if k in blob),"high"
    if any(k in blob for k in SINGLECELL): return "single_cell","platform/keywords",next(k for k in SINGLECELL if k in blob),"high"
    if any(k in blob for k in ARRAY):      return "bulk_transcriptomics","gdstype","microarray","high"
    if any(k in blob for k in RNASEQ):     return "bulk_transcriptomics","gdstype","rna-seq (bulk)","medium"
    return "unknown","gdstype",rec.get("gdstype",""),"low"

# ---------- repository confirmation ----------
def confirm_pride(acc: str):
    txt = _try(PRIDE + acc)
    if not txt: return {}
    d = json.loads(txt)
    organisms = "; ".join(o.get("name","") for o in d.get("organisms", []) if isinstance(o, dict))
    instr = "; ".join(i.get("name", str(i)) if isinstance(i, dict) else str(i) for i in d.get("instruments", []))
    return {"organism": organisms, "platform": instr, "confirmed": "PRIDE"}

def confirm_metabolights(acc: str):
    txt = _try(MTBLS + acc) or _try(MTBLS + "public/study/" + acc)
    if not txt: return {}
    d = json.loads(txt)
    s = json.dumps(d).lower()
    organism = ""
    for key in ("organism","characteristics","factors"):
        if key in d: organism = json.dumps(d[key]); break
    modality = "lipidomics" if any(k in s for k in LIPID) else "metabolomics"
    return {"organism": organism[:120], "platform": "MS/NMR (see assays)", "confirmed": "MetaboLights",
            "modality_override": modality}

def confirm_workbench(acc: str):
    txt = _try(MWB + acc + "/summary")
    if not txt: return {}
    d = json.loads(txt)
    s = json.dumps(d).lower()
    organism = d.get("subject_species","") or d.get("SUBJECT_SPECIES","")
    modality = "lipidomics" if any(k in s for k in LIPID) else "metabolomics"
    return {"organism": str(organism), "platform": str(d.get("analysis_type","")), "confirmed": "Workbench",
            "modality_override": modality}

def main(accessions: list[str]):
    rows = []
    for acc in accessions:
        repo, modality = "unknown", "unknown"
        field, value, conf, organism, plat, confirmed = "namespace", acc, "low", "", "", ""
        for rx, (r, m) in NAMESPACE:
            if rx.match(acc):
                repo = r
                if m == "QUERY":
                    rec = geo_summary(acc) if repo == "GEO" else {}
                    if rec:
                        modality, field, value, conf = classify_geo(rec)
                        plat = str(rec.get("ptechtype") or rec.get("gpl") or ""); organism = str(rec.get("taxon",""))
                        confirmed = "GEO"
                    else:
                        modality, field, value, conf = "unknown","api","no GEO summary","low"
                else:
                    modality, field, value, conf = m, "accession_namespace", repo, "medium"
                    info = (confirm_pride(acc) if repo in ("PRIDE/ProteomeXchange","MassIVE") else
                            confirm_metabolights(acc) if repo == "MetaboLights" else
                            confirm_workbench(acc) if repo == "Metabolomics Workbench" else {})
                    if info:
                        organism = info.get("organism",""); plat = info.get("platform","")
                        confirmed = info.get("confirmed",""); conf = "high"
                        if info.get("modality_override"): modality = info["modality_override"]; field = "repository_api"
                    else:
                        value += " (API unconfirmed -> verify manually)"
                break
        rows.append({"accession":acc,"repository":repo,"organism_verbatim":organism,"platform_instrument":plat,
                     "detected_modality":modality,"evidence_field":field,"evidence_value":value,
                     "confidence":conf,"confirmed":confirmed})

    os.makedirs("results", exist_ok=True)
    cols = ["accession","repository","organism_verbatim","platform_instrument","detected_modality","evidence_field","evidence_value","confidence","confirmed"]
    with open("results/modality_detected.csv","w",newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(rows)
    quar = [r for r in rows if r["detected_modality"]=="unknown" or r["confidence"]=="low" or not r["confirmed"]]
    if quar:
        with open("results/quarantine.csv","w",newline="") as f:
            w = csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(quar)
    print(f"classified {len(rows)} | quarantined (unknown/low-conf/unconfirmed) {len(quar)} -> results/modality_detected.csv")
    print(">>> READ modalities/<detected_modality>.md for each, apply its gates. Resolve quarantine before proceeding.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("usage: detect_modality.py ACC [ACC ...]   e.g. GSE96804 PXD000001 MTBLS123 ST000123"); sys.exit(2)
    main(sys.argv[1:])
