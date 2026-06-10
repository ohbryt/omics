---
name: reproducible-omics
description: >
  Use whenever collecting public omics datasets or running omics analysis for research —
  bulk RNA-seq/microarray, single-cell, spatial, MS proteomics, affinity proteomics
  (Olink/SomaScan), metabolomics, or lipidomics. Enforces deterministic, auditable pipelines.
  STEP 0 always auto-detects the dataset modality from structured metadata, then loads and
  applies the matching modality rules in modalities/. Trigger on: GEO/SRA/ArrayExpress, GSE/SRR,
  PRIDE/PXD/MassIVE, MetaboLights/MTBLS, Metabolomics Workbench, 10x/Visium/Xenium/MERFISH,
  Olink/SomaScan, scRNA-seq, spatial, proteomics, metabolomics, lipidomics, differential
  expression, dataset collection, or "omics reproducibility".
---

# Reproducible Omics — router + operating procedure

You orchestrate and write code; **you never compute or judge data in your head.** Reproducibility comes from deterministic code + a pinned environment + machine-checkable gates — not from your prose. **The analysis method is chosen by the detected modality, never assumed.**

## Non-negotiable rules (all modalities)
1. **No hand-computed results.** Every number (effect, p, FDR, count, n, direction) comes from an executed, committed script and is cited to its output file. Not computed → write and run the code; never estimate.
2. **No eyeballing for inclusion.** Dataset/sample inclusion is decided by code against **structured metadata fields**, never by reading a title/abstract.
3. **No fabrication.** Never invent accessions, platform/instrument IDs, feature IDs, versions, or statistics. Unknown → query the API. Query fails → say so and STOP.
4. **Detect before you analyze.** Never apply one modality's method to another's data (e.g., a transcriptomics DE pipeline to a proteomics or metabolomics table). If modality is ambiguous → quarantine and STOP.
5. **Stop-and-confirm.** After the modality + dataset audit tables and before processing, STOP for human sign-off (interactive) or emit STATUS and HALT (autonomous).

## STEP 0 — Auto-detect modality (always first)
Run `detect_modality.py` against the candidate accessions. It classifies each by **structured signals**: accession namespace (PXD/MSV/JPST → MS proteomics; MTBLS/ST → metabolomics; GSE/E-MTAB/SRR → query repository), repository, platform/instrument, `gdstype`/`library_strategy`, panel/file-type signatures. Output `results/modality_detected.csv` = `accession, repository, platform_instrument, detected_modality, evidence_field, evidence_value, confidence`. Ambiguous/unknown or low-confidence → `results/quarantine.csv`; do NOT proceed for those.

Then, **for each detected modality, READ the matching file in `modalities/` and apply its gates, fixed choices, statistics framing, and verifier assertions:**

| detected_modality | rules file |
|---|---|
| bulk transcriptomics (RNA-seq / microarray) | `modalities/bulk_transcriptomics.md` |
| single-cell (scRNA/snRNA-seq) | `modalities/single_cell.md` |
| spatial transcriptomics | `modalities/spatial.md` |
| MS proteomics (DDA/DIA) | `modalities/proteomics_ms.md` |
| affinity proteomics (Olink/SomaScan) | `modalities/affinity_proteomics.md` |
| metabolomics | `modalities/metabolomics.md` |
| lipidomics | `modalities/lipidomics.md` |

Never mix datasets of different modalities (or different platform classes within a modality) into one feature space; analyze each modality separately and integrate only with an explicit, justified method.

## STEP 1 — Selection gates
Universal: **organism gate** (include only exact members of `config.allowed_organisms`, default `{Homo sapiens, Mus musculus}`; dog/chicken/rat → auto-REJECT). Plus the **modality-specific gates** from the loaded rules file (assay/platform/panel/acquisition/ID-confidence, n, case/control). Write `results/dataset_audit.csv` with the decision and the field+value that triggered it.

## STEP 2 — Pin the environment
Lockfile (`renv.lock` / `environment.yml` + `conda-lock`) + container image digest; pin annotation/reference/library versions; set+record seeds; one-command pipeline regenerates all outputs (checksum-identical). Commit raw/frozen inputs + `data/CHECKSUMS.txt`.

## STEP 3-4 — Processing + statistics
Use **only** the fixed analysis choices and significance framing defined in the loaded modality file (they differ: genome-wide BH-FDR for transcriptomics; target-decoy FDR for MS proteomics; ID-confidence + drift correction for metabolomics/lipidomics; pseudobulk for single-cell; segmentation/deconvolution for spatial; LOD/normalization for affinity proteomics). Cross-dataset combination only via standardized-effect random-effects meta or a justified integration method — **never vote-counting**.

## STEP 5 — Verifier (`scripts/verify.py`, fail loudly)
Assert the universal gates (organism ∈ allowed; IDs well-formed; env pinned; run-config matches; checksums match) **plus the modality-specific assertions** listed in the loaded rules file. Print PASS/FAIL and emit STATUS (PASS / BLOCKED / NEEDS_REVIEW). Done only when verify passes.

## STEP 6 — Output contract
Deliver committed code + config used + `modality_detected.csv` + `dataset_audit.csv` + result tables with checksums + a claim→file map. **No claim without a file behind it.**

## Anti-patterns (refuse)
- Proceeding without Step 0 detection; applying a modality's method to another modality's data.
- Selecting datasets by reading abstracts; including non-allowed organisms; mixing platform classes (e.g., Visium whole-transcriptome with Xenium targeted panel; Olink NPX with SomaScan RFU; DDA with DIA) into one feature space.
- Reporting reasoned numbers instead of computed ones; pooling by "X up / Y down"; guessing accessions/versions; declaring success before verify passes.

## Companion files
- `detect_modality.py` — Step 0 classifier template.
- `dataset_selection_gate.py` — Step 1 selection template (organism + modality gates).
- `scripts/verify.py`, `Snakefile`, `config.yaml`, `environment.yml`, `CLAUDE.md`, `automated_run_operating_instruction.md`.
