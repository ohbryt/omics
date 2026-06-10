# CLAUDE.md — Rules for LLM-Assisted Omics (reproducible, validated)

These rules are binding for any agent working in this repository. The goal is **deterministic, reproducible, auditable** omics analysis. The agent **orchestrates and writes code; it does not compute or judge data in its head.**

## 0. Non-negotiables (read first)

1. **No hand-computed results.** Never state a number you derived by reasoning — fold change, p value, FDR, sample size, dataset count, gene direction, anything. Every number must come from an executed, committed script's output file/stdout, and you must cite that file.
2. **No eyeballing for inclusion.** Dataset and sample inclusion/exclusion is decided by code against **structured metadata fields**, never by reading an abstract or a title.
3. **No fabrication.** Never invent accession numbers (GSE/GSM/SRR), platform IDs (GPL), gene IDs, or statistics. If unknown, query the API. If a query fails, say so and stop.
4. **Fail closed.** A dataset enters analysis only if repository metadata, platform metadata, raw-data evidence, and publication evidence all agree. Any conflict → reject or quarantine with logged discrepancy.
5. **Detect before you analyze.** Never apply one modality's method to another's data. If modality is ambiguous → quarantine and STOP.
6. **Stop-and-confirm.** After producing the dataset audit table and before running differential expression, STOP and require human sign-off.

## 1. Three-layer species gate

Every included dataset must pass all three layers:

| Layer | Check | Method |
|---|---|---|
| 1: Repository metadata | Canonical species field = allowed organism | API query to GEO/BioStudies/SRA |
| 2: Platform agreement | Platform annotation consistent with species | Platform/GPL metadata check |
| 3: Empirical verification (RNA-seq) | Raw reads classify to allowed species | FastQ Screen + Kraken2 against multi-genome panel |

For human sequencing: add verifyBamID2 (contamination) + CrosscheckFingerprints (identity).

## 2. Publication cross-check

Require PMID or DOI (or explicit "citation missing" flag). Verify repository record matches paper on: accession, species, tissue, sample count, perturbation, platform.

## 3. Raw-file presence

- RNA-seq: require FASTQ/SRA/BAM. Processed count matrices alone → downgrade to exploratory.
- Microarray: require CEL/IDAT. Normalised-only matrices → acceptable with documented caveat.

## 4. Dataset selection = hard programmatic gates

Query metadata via API only. Apply gates **in code** to structured fields and write `results/dataset_audit.csv`:

- **Organism gate:** exact match to `config.allowed_organisms` (default: Homo sapiens, Mus musculus). Anything else → auto-REJECT.
- **Platform/assay gate:** match `config.required_assay`. Never mix microarray with RNA-seq.
- **Audit row per accession:** includes species verification layers, publication match, raw-data presence, decision, trigger field+value.
- **Human sign-off** on audit CSV before any downstream step.

## 5. Determinism and environment

- Pin everything: lockfile + container image digest (SHA256); pin annotation package versions; set+record seeds.
- One-command pipeline regenerates all outputs from accession list. Same commit → checksum-identical results.
- Commit raw matrices + `data/CHECKSUMS.txt`.
- Version code in Git, data in DataLad, provenance in RO-Crate.

## 6. Technology-specific QC

### Microarray
- Array-level QC: `arrayQualityMetrics`, RLE, NUSE, percent present, RNA degradation
- Exclude arrays with **logged rationale** from cohort-aware diagnostics
- Fixed normalization (RMA) + fixed probe→gene collapse (jetset/max-mean)

### RNA-seq
- FastQC + MultiQC for raw-read QC
- FastQ Screen + Kraken2 for species origin
- RNA-SeQC 2 + RSeQC for alignment/expression QC
- verifyBamID2 + CrosscheckFingerprints for contamination/identity
- ENCODE-informed thresholds: ≥30M reads, ≥2 replicates, Spearman ≥0.9 (isogenic)

### Batch handling
- **Detect before correct**: PCA/MDS, BatchQC, PVCA, variancePartition
- Correction method matched to data type (ComBat, ComBat-seq, SVA, RUVSeq, or model in design)
- `limma::removeBatchEffect` for visualisation ONLY — never for DE testing

## 7. Microarray-specific rules

- Fixed normalization, background correction, probe-collapse rule — all in config
- Pinned platform annotation package + version
- Never pool across platforms by vote-counting. Combine via standardized-effect random-effects meta (report I²).

## 8. Statistics and reporting

- Genome-wide Benjamini-Hochberg FDR < 0.05 across all features. Record in config.
- Report effect size + CI/SE + FDR from script. Direction from computed value.
- Tissue mRNA/omics is biological context, not validation of a circulating biomarker.

## 9. LLM guardrails

- The LLM is a **candidate generator**, never the gatekeeper
- XML-structured prompts with JSON output schema
- Local Pydantic validation before any LLM output enters the workflow
- The model may NEVER relax a hard constraint
- Prompt chaining for auditability: discovery → extraction → contradiction → report
- Reproducibility test: same accession set + same prompt → diff outputs; fail if inclusion drifts

## 10. Verifier (fail loudly)

`scripts/verify.py` asserts and exits non-zero on any violation:
- Every included dataset's organism in allowed_organisms
- Every included dataset's technology matches required_assay
- Three-layer species gate passed (Layer 3 for RNA-seq)
- Publication cross-check recorded
- Raw-file presence recorded; downgrade flags set where applicable
- No accession/GPL/gene ID missing or malformed
- FDR computed genome-wide; probe-collapse rule == config
- Batch detected before correction; correction method recorded
- QC metrics recorded; MultiQC report present
- Result checksums match committed values
- Container pinned by digest; env locked

Print PASS/FAIL count. Pipeline is "done" only when verify passes.

## 11. Human checkpoints

- **Checkpoint A:** approve `dataset_audit.csv` + `modality_detected.csv` before processing
- **Checkpoint B:** approve DE parameters (normalization, collapse rule, model, FDR, batch handling) before synthesis
- **Checkpoint C:** bioinformatician re-runs pipeline or independently re-derives ≥1 dataset

## 12. Output contract

Committed code + config + modality CSV + audit CSV + result tables with checksums + MultiQC report + claim→file map. **No claim without a file behind it.**

## 13. What the agent should output

The exact code (committed), the config used, the audit CSV, the modality CSV, result tables with checksums, MultiQC report, and a short log mapping each claim to its source file/line. **No claim without a file behind it.**
