# Modality: Bulk transcriptomics (RNA-seq / microarray)

**Detection signals.** GEO `gdstype` = "Expression profiling by array" (microarray) or "...by high throughput sequencing" without single-cell/spatial signatures; SRA `library_strategy=RNA-Seq` (bulk). Repositories: GEO, ArrayExpress, SRA, recount3, BioStudies.

**Never allow microarray and RNA-seq to share a preprocessing branch.** They have different metadata standards, raw files, normalisation methods, QC regimes, and batch-effect behaviour.

## Selection gates (+ universal organism gate)

- assay ∈ {microarray, rna-seq} and equals `config.required_assay`.
- platform/GPL recorded; n per group ≥ `min_n`; case/control present.
- **Three-layer species gate** (see SKILL.md Step 1A):
  - Layer 1: repository metadata says allowed species
  - Layer 2: platform annotation agrees
  - Layer 3 (RNA-seq only): FastQ Screen / Kraken2 confirms dominant classification to allowed species
- **Publication cross-check**: repository record matches paper on species, tissue, sample count, accession
- **Raw-file presence**: FASTQ/SRA/BAM for RNA-seq; CEL/IDAT for microarray. Processed-only → downgrade to exploratory.

## Fixed analysis choices (pin + declare)

### Microarray branch

- **Normalization**: RMA (fixed, not per-run) + background correction
- **Probe→gene collapse rule** (jetset/max-mean) applied identically across datasets
- **Pinned platform annotation package version** (annotations drift between releases)
- **Explicit batch handling** (see batch section below)
- **Array-level QC** before DE:

| Metric | Method | Action threshold |
|---|---|---|
| Outlier diagnostics | `arrayQualityMetrics` | Arrays inconsistent with cohort (distance, intensity, MA) → flag |
| Percent present / scale factor | Affymetrix QC | Scale factor >3-fold across cohort → warning |
| 3′/5′ ratios, RNA degradation | GAPDH/β-actin ratios | Ratio >3 or profile diverging from cohort → flag |
| RLE / NUSE | `affyPLM` | Median NUSE >1.05 warning; >1.25 strong reject signal |

Excluded arrays must have **logged rationale** based on cohort-aware diagnostics, not ad hoc judgment.

### RNA-seq branch

- **Fixed aligner/quantifier + reference genome + versions** (e.g., STAR + GENCODE v44 + GRCh38)
- **DE method fixed** (DESeq2 / edgeR / limma-voom); low-count filter stated
- **Raw-read QC** before alignment:

| Metric | Method | Threshold (ENCODE-informed) |
|---|---|---|
| Raw-read quality | FastQC + MultiQC | Per-base quality, adapters, GC bias, overrepresented sequences |
| Species origin | FastQ Screen + Kraken2 | Dominant classification to allowed species |
| Read depth | Alignment counting | ≥30M aligned reads per bulk replicate |
| Replicate concordance | Gene-level Spearman | ≥0.9 isogenic, ≥0.8 anisogenic |
| Alignment / expression QC | RNA-SeQC 2 + RSeQC | Mapping rate, rRNA%, gene-body coverage, 3′/5′ bias |
| RNA integrity | RSeQC inner distance, gene-body coverage | Detect degraded RNA, library prep problems |
| Contamination / swaps | verifyBamID2 + CrosscheckFingerprints | Contamination >threshold → REJECT; fingerprint mismatch → REJECT |

### Cross-dataset combination

- Per-dataset **standardized effect + random-effects meta-analysis** (report I²)
- **Never vote-counting** ("X up / Y down")
- Never pool across platforms without harmonization

## Batch handling (detect BEFORE correction)

### Detection

1. PCA/MDS plots coloured by suspected batch factors
2. Sample-clustering heatmaps
3. Quantitative estimation: BatchQC, PVCA, or variancePartition → fraction of variance attributable to batch vs biology
4. If batch dominates principal components or variance fractions → **document explicitly** before any correction

### Correction methods (match to data type)

| Method | Data type | When to use |
|---|---|---|
| Model batch in DE design matrix | Both | **First choice** when batch is known and modelable |
| ComBat | Normalised continuous expression | Known batch; normalised microarray or log-transformed |
| ComBat-seq | RNA-seq counts | Known batch; count-level correction |
| SVA | Both | Latent/unknown unwanted factors |
| RUVSeq | RNA-seq | Control genes or replicate structure available |
| `limma::removeBatchEffect` | Both | **Visualisation/unsupervised plots ONLY** — the limma documentation explicitly states it is not intended to replace proper linear modelling for DE testing |

## Statistics framing

- Genome-wide Benjamini-Hochberg FDR < 0.05 across all genes (not a within-gene-set FDR)
- Report effect size + SE/CI + FDR from the script
- Direction (up/down) from the computed value, not assumption

## Biggest non-determinism risks

- Probe-collapse choice; annotation version drift; normalization method
- Batch/cohort effects; reference/annotation version (RNA-seq)
- Array QC outlier decisions (cohort-dependent, not universal threshold)

## Verifier assertions (add to verify.py)

- assay == required; probe_collapse_rule == config (microarray)
- annotation/reference version recorded; FDR genome-wide
- No platform mixing in a pooled set; meta used (not vote-counting)
- Three-layer species gate passed (Layer 3 for RNA-seq)
- Publication cross-check result recorded
- Raw-file presence recorded; downgrade flag if processed-only
- Batch detection documented before correction; correction method == config
- QC metrics recorded (MultiQC report present)

## Anti-patterns

- Mixing microarray + RNA-seq (or different arrays) in one matrix
- Collapsing probes differently per dataset
- Counting "X up / Y down" across datasets
- Using `limma::removeBatchEffect` as a substitute for batch-modelling in DE
- Correcting batch before detecting and documenting it
- Trusting processed-only matrices without raw-data verification
- Inferring platform from title instead of repository/platform metadata
- Including a species based on title/abstract without empirical verification
