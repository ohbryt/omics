# reproducible-omics — one self-contained folder

Deterministic, auditable, **modality-aware** omics pipeline + skill. The agent orchestrates and
writes code; determinism and correctness live in the code, the pinned environment, and the
verifier — not in the model's prose. **It detects the dataset modality first, then applies the
matching rules.**

## Everything is in this folder
```
reproducible-omics/
  SKILL.md                              # router skill: rules + STEP 0 detect + dispatch to modalities/
  CLAUDE.md                             # always-on repo rules
  automated_run_operating_instruction.md# seed prompt for unattended/autonomous runs
  config.yaml                           # single source of truth (organisms, assay, FDR, collapse rule, paths)
  config/accessions.txt                 # YOU list the accessions to process (one per line)
  config/grouping/<ACC>.csv             # YOU provide case/control per dataset (sample_id,group)
  environment.yml                       # pinned conda/Bioconductor env (freeze to environment.lock.yml)
  Snakefile                             # detect -> select -> env -> process -> meta -> checksums -> verify
  detect_modality.py                    # STEP 0: classify + confirm via GEO/PRIDE/MetaboLights/Workbench APIs
  dataset_selection_gate.py             # STEP 1: organism + modality gates -> results/dataset_audit.csv
  modalities/                           # per-modality gates, fixed choices, stats, verifier assertions
    bulk_transcriptomics.md  single_cell.md  spatial.md  proteomics_ms.md
    affinity_proteomics.md   metabolomics.md  lipidomics.md
  scripts/
    verify.py                           # TERMINAL GATE: universal + per-modality assertions; emits STATUS
    record_run_config.py  00_checksums.py
    02_differential_expression.R  03_meta_analyze.R
  results/                              # generated (audit, modality_detected, de/, method/, meta, checksums)
```

## Run
```bash
conda env create -f environment.yml && conda activate reproducible-omics   # then freeze environment.lock.yml
# 1) list accessions in config/accessions.txt (GSE.../PXD.../MTBLS.../ST...)
# 2) edit config.yaml (allowed_organisms, required_assay, FDR, collapse rule)
snakemake -c4 --use-conda          # detect -> gate -> process -> verify; fails if verify does not pass
# or step through:
python detect_modality.py GSE96804 PXD000001 MTBLS123      # STEP 0
python dataset_selection_gate.py                            # STEP 1
python scripts/verify.py                                    # terminal gate
```

## How modality routing works
1. `detect_modality.py` classifies each accession by **structured signals** (accession namespace,
   repository, GEO gdstype/platform, 10x/Visium/Xenium/Olink signatures) and **confirms via the
   owning repository's API** (E-utilities / PRIDE / MetaboLights / Metabolomics Workbench), capturing
   the verbatim organism and platform and sub-detecting lipidomics inside metabolomics.
   Ambiguous / low-confidence / API-unconfirmed -> `results/quarantine.csv` and STOP.
2. For each detected modality, read `modalities/<modality>.md` and apply its gates, fixed analysis
   choices, statistics framing, and the verifier assertions it lists.
3. Each processing step writes a **method record** (`results/method/<acc>.json` or
   `results/de/<acc>_method.json`) capturing the fixed choices; `verify.py` asserts the required keys
   per modality (e.g., single-cell: seed + integration version + frozen annotation reference +
   `de_method=pseudobulk`; MS proteomics: search engine/FASTA versions + `fdr_type=target_decoy` +
   imputation method; metabolomics/lipidomics: tool/version + drift correction + ID-confidence level).

## "Done" means
`python scripts/verify.py` exits 0 and prints **STATUS=PASS**, every number is file-backed, and
`results/dataset_audit.csv` + `results/modality_detected.csv` show every decision with the field+value
that drove it. `STATUS=BLOCKED` / `NEEDS_REVIEW` means a human must look before anything is trusted.

## To finish wiring (intentional TODOs)
1. Fill the marked steps in `scripts/02_differential_expression.R` (raw-CEL RMA + pinned-annotation
   collapse / RNA-seq quant) and add per-modality processing scripts that emit `results/method/<acc>.json`.
2. Provide `config/accessions.txt` and `config/grouping/<ACC>.csv`.
3. Set your `EMAIL` in `detect_modality.py`; freeze `environment.lock.yml` and pin annotation/reference/
   library versions per modality.
