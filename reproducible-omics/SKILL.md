---
name: reproducible-omics
description: >
  Use whenever collecting public omics datasets or running omics analysis for research —
  bulk RNA-seq/microarray, single-cell, spatial, MS proteomics, affinity proteomics
  (Olink/SomaScan), metabolomics, or lipidomics. Enforces deterministic, auditable pipelines
  with three-layer species verification, publication cross-checks, raw-file gates,
  technology-specific QC, batch detection-before-correction, and LLM guardrails.
  STEP 0 always auto-detects the dataset modality from structured metadata, then loads and
  applies the matching modality rules in modalities/. Trigger on: GEO/SRA/ArrayExpress, GSE/SRR,
  PRIDE/PXD/MassIVE, MetaboLights/MTBLS, Metabolomics Workbench, 10x/Visium/Xenium/MERFISH,
  Olink/SomaScan, scRNA-seq, spatial, proteomics, metabolomics, lipidomics, differential
  expression, dataset collection, or "omics reproducibility".
---

# Reproducible Omics — Router + Operating Procedure

You orchestrate and write code; **you never compute or judge data in your head.**
Reproducibility comes from deterministic code + a pinned environment + machine-checkable gates — not from your prose.
**The analysis method is chosen by the detected modality, never assumed.**

## Non-negotiable Rules (All Modalities)

1. **No hand-computed results.** Every number (effect, p, FDR, count, n, direction) comes from an executed, committed script and is cited to its output file. Not computed → write and run the code; never estimate.
2. **No eyeballing for inclusion.** Dataset/sample inclusion is decided by code against **structured metadata fields**, never by reading a title/abstract.
3. **No fabrication.** Never invent accessions, platform/instrument IDs, feature IDs, versions, or statistics. Unknown → query the API. Query fails → say so and STOP.
4. **Detect before you analyze.** Never apply one modality's method to another's data (e.g., a transcriptomics DE pipeline to a proteomics or metabolomics table). If modality is ambiguous → quarantine and STOP.
5. **Fail closed.** A dataset enters analysis only if repository metadata, platform metadata, raw-data evidence, and publication evidence **all agree**. If any layer conflicts, either reject automatically or move to manual-review queue with the discrepancy logged. Processed-only datasets with weak or missing raw-data links are **downgraded** — they may be used for exploratory review but must not drive final biological claims unless the limitation is explicit.
6. **Stop-and-confirm.** After the modality + dataset audit tables and before processing, STOP for human sign-off (interactive) or emit STATUS and HALT (autonomous).

## STEP 0 — Auto-detect Modality (Always First)

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

## STEP 1 — Selection Gates (Fail-Closed, Three-Layer Species Verification)

### 1A. Three-layer species gate

Every included dataset must pass **all three layers**. Failure at any layer → REJECT or quarantine.

| Layer | Check | Method |
|---|---|---|
| **Layer 1: Repository metadata** | Canonical species field in GEO/BioStudies/SRA/ENA record equals a member of `config.allowed_organisms` | Parse structured metadata via API. Accept only `Homo sapiens` or `Mus musculus`. Common names and free-text variants → normalise or reject. |
| **Layer 2: Platform/assay agreement** | Platform or assay metadata agrees with the species declared at Layer 1 | Platform annotation must be consistent. E.g., a human GPL paired with mouse organism → flag conflict → quarantine. |
| **Layer 3: Empirical species verification** (RNA-seq only) | Raw reads classify/map predominantly to an allowed species | Run **FastQ Screen** against a multi-genome panel (human, mouse, dog, chicken, PhiX, rRNA contaminants) and/or **Kraken2** with standard database. Require dominant classification to human or mouse. |

For human sequencing, add **identity and contamination checks**:
- **verifyBamID2** — estimate contamination from BAM/CRAM when available
- **CrosscheckFingerprints** (Picard) — confirm related files come from the same individual

Any sample failing Layer 3 → REJECT with reason logged. Multi-organism series must be a subset of allowed or REJECT entirely.

### 1B. Publication cross-check

Require a publication link (PMID or DOI) or an explicit "citation missing" flag. Then verify:
- Title, species, tissue, disease, sample count, and accession mention match between repository record and paper
- Discrepancies → quarantine with logged discrepancy; do not silently include

### 1C. Raw-file presence gate

| Assay | Required raw files | Downgrade rule |
|---|---|---|
| RNA-seq | FASTQ / SRA / BAM | Processed count matrices alone → downgrade to exploratory; do not enter primary DE pipeline |
| Microarray (Affymetrix) | CEL files | Normalised matrices alone → acceptable only with documented caveat; prefer raw CELs for true RMA |
| Microarray (Illumina) | IDAT files | Same downgrade rule |

### 1D. Write audit outputs

Write `results/dataset_audit.csv` with columns: `accession, organism_verbatim, platform_GPL, gdstype, assay_detected, n_total, n_case, n_control, tissue, species_layer1, species_layer2, species_layer3, publication_match, raw_data_present, decision(INCLUDE/REJECT/DOWNGRADE/QUARANTINE), trigger_field, trigger_value, confidence`. Every non-INCLUDE decision names the field+value that triggered it.

**Human sign-off** on the audit CSV (record approver + date) before any downstream step.

## STEP 2 — Pin the Environment (Determinism)

Lockfile (`renv.lock` / `environment.yml` + `conda-lock`) + container image digest (pin by SHA256, not tag); pin annotation/reference/library versions; set+record seeds; one-command pipeline regenerates all outputs (checksum-identical). Commit raw/frozen inputs + `data/CHECKSUMS.txt`.

### Workflow architecture

| Component | Recommended role | Why |
|---|---|---|
| **Nextflow** | Production orchestration (workstation, HPC, cloud) | Scalable, portable, container-native |
| **Snakemake** | Leaner alternative, R-heavy custom workflows | Auto-deploys dependencies, reproducible |
| **nf-core conventions** | Style guide and quality floor | Encodes bioinformatics best practices |
| **MultiQC** | Aggregate all QC logs into one report | Single view across FastQC, RNA-SeQC, arrayQualityMetrics, etc. |
| **Git** | Version code, configs, prompts, manifests | Distributed version control |
| **DataLad** | Version large raw/derived datasets | Git + git-annex; tracks data provenance |
| **RO-Crate** | Capture workflow-run provenance | Inputs, outputs, environment in one package |

## STEP 3 — Technology-Specific QC (Before Processing)

### 3A. Microarray QC

| Metric | Method | Action |
|---|---|---|
| Array-level outlier diagnostics | `arrayQualityMetrics` | Flag arrays inconsistent with cohort (distance, intensity, MA) |
| Percent present / scale factor | Affymetrix QC | Scale factors >3-fold across cohort → warning |
| 3′/5′ ratios, RNA degradation | GAPDH/β-actin ratios, degradation slopes | Ratio >3 or profile diverging from cohort → flag |
| RLE / NUSE | `affyPLM` | Median NUSE >1.05 (warning) or >1.25 (strong reject signal) |

Excluded arrays must have **logged rationale** based on cohort-aware diagnostics, not ad hoc judgment.

### 3B. RNA-seq QC

| Metric | Method | Threshold (ENCODE-informed) |
|---|---|---|
| Raw-read quality | FastQC + MultiQC | Per-base quality, adapters, GC bias, overrepresented sequences |
| Species origin | FastQ Screen + Kraken2 | Dominant classification to allowed species |
| Read depth | Alignment counting | ≥30M aligned reads per bulk replicate |
| Replicate concordance | Gene-level Spearman | ≥0.9 isogenic, ≥0.8 anisogenic |
| Alignment / expression QC | RNA-SeQC 2 + RSeQC | Yield, mapping rate, rRNA%, gene-body coverage, 3′/5′ bias |
| RNA integrity from sequence | RSeQC inner distance / gene-body coverage | Detect degraded RNA, library prep problems |
| Contamination / swaps | verifyBamID2 + CrosscheckFingerprints | Contamination >threshold → REJECT; fingerprint mismatch → REJECT |

### 3C. Batch handling (detect BEFORE correction)

1. **Detect**: PCA/MDS plots, sample-clustering heatmaps, BatchQC / PVCA / variancePartition to estimate variance attributable to technical factors vs biology
2. **Document**: If batch dominates principal components or variance fractions, record explicitly before correction
3. **Correct with method matched to data type**:

| Method | Data type | When to use |
|---|---|---|
| Model batch in DE design matrix | Both | First choice when batch is known and modelable |
| ComBat | Normalised continuous expression | Known batch, normalised microarray or log-transformed RNA-seq |
| ComBat-seq | RNA-seq counts | Known batch, count-level correction |
| SVA | Both | Latent/unknown unwanted factors |
| RUVSeq | RNA-seq | Control genes or replicate structure available |
| `limma::removeBatchEffect` | Both | Visualisation/unsupervised plots ONLY — not for DE testing |

## STEP 4 — Processing + Statistics

Use **only** the fixed analysis choices and significance framing defined in the loaded modality file. Cross-dataset combination only via standardized-effect random-effects meta-analysis (report I²) or a justified integration method — **never vote-counting** ("X up / Y down").

## STEP 5 — Verifier (`scripts/verify.py`, fail loudly)

Assert the **universal gates** (organism ∈ allowed; IDs well-formed; env pinned; run-config matches; checksums match) **plus the modality-specific assertions** listed in the loaded rules file.

Additional universal assertions from this upgrade:

- Every included dataset has stable study accession + sample accession + platform/assay identifier
- Species stored as canonical scientific name (not common name)
- Platform class assigned from repository/platform metadata (not title)
- Raw data present and linked (FASTQ/CEL/IDAT or documented exception)
- Publication linkage verified (or explicit "citation missing" flag)
- RNA-seq samples passed empirical species-origin check
- Human samples passed contamination/identity checks where technically possible
- Batch assessed before correction; correction method recorded
- QC aggregated in MultiQC report
- Clean rerun reproduces accession set + QC summary + core outputs (checksum-identical)

Print PASS/FAIL and emit STATUS (PASS / BLOCKED / NEEDS_REVIEW). Done only when verify passes.

## STEP 6 — Output Contract

Deliver committed code + config used + `modality_detected.csv` + `dataset_audit.csv` + result tables with checksums + MultiQC report + a claim→file map. **No claim without a file behind it.**

## LLM Guardrails

The LLM is a **candidate generator**, never the gatekeeper of species, platform, provenance, or QC. A deterministic validator is the final decision-maker.

### Prompt structure
- Use **XML-structured prompts** separating role, hard constraints, input, instructions, and output schema
- Require **JSON output** matching a strict schema
- Validate locally with **Pydantic** or equivalent before any output enters the workflow
- The model may NEVER relax a hard constraint. Missing/conflicting evidence → `include=false`

### Prompt chaining (for auditability)
Split LLM work into discrete prompts:
1. Candidate discovery
2. Metadata extraction
3. Contradiction detection
4. Report generation

Each decision is attributable to a narrower task, making audits tractable.

### LLM reproducibility testing
Run the same accession set through the same prompt version multiple times. Diff the structured outputs. Fail the pipeline if inclusion sets or rejection reasons drift unexpectedly.

### Output schema (study triage)

```json
{
  "accession": "string",
  "repository": "string",
  "platform_class": "microarray|RNA-seq|unknown",
  "species_metadata": "Homo sapiens|Mus musculus|other|unknown",
  "species_empirical": "Homo sapiens|Mus musculus|other|not_applicable|unknown",
  "publication_match": "bool",
  "raw_data_present": "bool",
  "include": "bool",
  "confidence": "float",
  "rejection_reasons": ["string"],
  "evidence": {
    "platform_field": "string",
    "species_field": "string",
    "publication_identifier": "string",
    "raw_file_types": ["string"]
  }
}
```

## Ingestion Checklist (Hard Gate)

Before any dataset enters the primary analysis pipeline, ALL of these must pass:

- [ ] Every included dataset has a stable study accession, sample accession, and platform/assay identifier recorded in a manifest
- [ ] Species is stored as canonical scientific name and is exactly an allowed organism; common-name and free-text variants normalised or rejected
- [ ] Platform class assigned deterministically as `microarray` or `RNA-seq` from repository/platform metadata, not guessed from study title
- [ ] Raw data present and linked: FASTQ/SRA/BAM for RNA-seq, CEL/IDAT for microarray where available; processed-only datasets downgraded
- [ ] Publication linkage verified; paper agrees with repository record on accession, species, tissue, perturbation, and sample count
- [ ] RNA-seq samples passed empirical species-origin checks with multi-genome screen; human alignments passed contamination and identity checks where technically possible
- [ ] Microarray samples passed array-level QC; excluded arrays have logged reasons based on cohort-aware diagnostics
- [ ] RNA-seq libraries met study-appropriate read-depth, replicate, and concordance standards (ENCODE-style thresholds where applicable)
- [ ] Batch structure assessed before correction; correction method matched to data type; batch variables preserved in final metadata
- [ ] Full run versioned: code in Git, data in DataLad or equivalent, QC aggregated in MultiQC, provenance captured in RO-Crate, containers pinned by digest
- [ ] LLM output is XML-structured on input, JSON-structured on output, locally schema-validated, and unable to override hard scientific constraints
- [ ] Clean rerun from frozen workflow reproduces the accession set, QC summary, and core quantitative outputs

## Anti-patterns (Refuse)

- Proceeding without Step 0 detection; applying a modality's method to another modality's data
- Selecting datasets by reading abstracts; including non-allowed organisms; mixing platform classes into one feature space
- Trusting metadata at face value without empirical species verification (RNA-seq) or array-level QC (microarray)
- Pooling across platforms by "X up / Y down"; guessing accessions/versions; declaring success before verify passes
- Using `limma::removeBatchEffect` for DE testing (visualisation only)
- Letting the LLM override hard scientific constraints (species, platform, QC gates)
- Processing processed-only datasets in the primary pipeline without documenting the limitation
- Correcting batch effects before detecting and documenting them

## Entity Model

Datasets are **linked entities**, not flat matrices. Enforce the entity model in all manifests:

```
PUBLICATION → STUDY → SERIES → SAMPLE → RAW_FILE / PROCESSED_FILE / QC_REPORT
                       SERIES → PLATFORM
                       SERIES → BATCH_FACTOR
              STUDY → PROVENANCE_RUN → SOFTWARE_ENV → CONTAINER_IMAGE
```

Every sample must have a parent study accession, a sample accession, and a platform/assay identifier. Reject orphaned files.

## Companion Files

- `detect_modality.py` — Step 0 classifier template
- `dataset_selection_gate.py` — Step 1 selection template (three-layer species + publication + raw-file gates)
- `modalities/` — per-modality gates, fixed choices, stats, verifier assertions
- `scripts/verify.py`, `Snakefile`, `config.yaml`, `environment.yml`, `CLAUDE.md`, `automated_run_operating_instruction.md`
