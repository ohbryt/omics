# GTEx / Omics QC Requirements and Skill Review

Date: 2026-06-10

## Purpose

This note consolidates the current review of the `reproducible-omics` skill/pipeline and the practical needs that motivated it.

The main problem is not just that Claude/Codex may choose the wrong dataset. In GTEx, bulk RNA-seq, and single-cell RNA-seq work, automated analysis often fails because human analysts apply many sample-, feature-, and cell-level QC rules before modeling, while an AI runner may pass raw or weakly filtered data directly into downstream statistics.

The target is therefore:

- deterministic dataset selection;
- deterministic modality detection;
- deterministic sample, feature, and cell QC;
- auditable exclusion decisions;
- explicit handling of `0`, `NA`, and `"not applicable"`;
- method records for every normalization, imputation, outlier, and doublet decision;
- verifier checks that fail loudly before any result is trusted.

## Current Skill Direction

The current skill is strong in these areas:

- It states that the LLM must orchestrate and write code, not compute or judge omics data in its head.
- It requires dataset inclusion/exclusion by code against structured metadata.
- It requires organism and assay gates.
- It adds modality detection before analysis.
- It requires audit tables, checksums, pinned environments, and `STATUS=PASS / BLOCKED / NEEDS_REVIEW`.
- It separates bulk transcriptomics, single-cell, spatial, proteomics, affinity proteomics, metabolomics, and lipidomics rules.

The current gap is that it is still weighted toward dataset-level reproducibility. GTEx/scRNA mistakes usually happen later, at sample, feature, cell, outlier, and missing-value handling.

## Review Findings From This Folder

### High Priority

1. Stop-and-confirm is documented but not enforced by the execution graph.

   The root `Snakefile` can proceed from selection into differential expression and verification. A real gate should require a signed approval artifact after `results/dataset_audit.csv`, and downstream rules should depend on that approval file.

2. The verifier fails on Windows because text encoding is not explicit.

   Scripts such as `scripts/verify.py`, `scripts/record_run_config.py`, and `scripts/00_checksums.py` call `read_text()` without `encoding="utf-8"`. In the current Windows/Codex environment, `python scripts\verify.py` failed before reaching the gate logic.

3. `dataset_selection_gate.py` does not use `config.yaml` as the single source of truth.

   It has an internal `CONFIG` block and does not consume the modality detection output. This weakens the documented contract that config controls allowed organisms, assay, thresholds, and paths.

4. Empty audit tables can be treated as partial success.

   With UTF-8 mode enabled, the verifier recognized an empty `dataset_audit.csv` as present. A zero-row audit should normally be `BLOCKED` unless the run is explicitly configured as a dry template run.

5. The root folder and `reproducible-omics/` folder have diverged.

   The self-contained `reproducible-omics/` copy includes modality detection in the Snakemake order, while the root pipeline is older. One canonical implementation should be chosen to avoid agents following the wrong copy.

### Medium Priority

1. Modality detection still uses title/summary keyword signals in places.

   Those fields are useful for routing hints, but the final gate should rely on structured repository metadata wherever possible.

2. The skill zip contains both the full `reproducible-omics/` folder and the smaller `reproducible-omics-skill/` folder.

   The intended install root should be unambiguous. Generated placeholder results should not be treated as real outputs.

3. The current `verify.py` has only limited modality-specific checks.

   It should assert the required QC artifacts and method-record keys for GTEx/bulk and single-cell workflows.

## User Requirements Captured So Far

### GTEx / Bulk RNA-seq

The automated workflow must not analyze GTEx samples simply because they appear in a downloaded expression matrix. It must first audit and decide on sample inclusion using structured metadata and computed QC metrics.

Required concerns:

- RIN / RNA integrity;
- ischemic time when available;
- mapping rate;
- duplication rate;
- rRNA or mitochondrial fraction where available;
- library size / sequencing depth;
- tissue and donor metadata consistency;
- expression-based sample outliers;
- batch variables and covariates;
- whether low-quality metrics trigger exclusion or covariate modeling.

The workflow should produce:

- `results/sample_qc_audit.csv`
- `results/feature_qc_audit.csv`
- `results/outlier_audit.csv`
- `results/qc_method.json`
- `results/run_config_used.json`

### `0`, `NA`, and `"not applicable"`

The pipeline must never collapse these into a single generic missing value without a recorded rule.

Required distinctions:

- biological zero;
- technical zero;
- below detection limit;
- true missing;
- not applicable;
- imputation placeholder;
- unavailable metadata.

Required rules:

- define allowed missingness thresholds in `config.yaml`;
- remove samples/features above configured missingness thresholds;
- only impute when the configured conditions allow it;
- record imputation method, version, target matrix, and whether imputed values are down-weighted;
- mark imputed values so downstream claims can be traced.

The workflow should produce:

- `results/missingness_audit.csv`
- `results/imputation_audit.csv`
- method records including `zero_policy`, `na_policy`, `not_applicable_policy`, `imputation_method`, and `imputed_value_weighting`.

### Outlier Handling

Outliers should not be removed by an LLM looking at a plot. Outlier detection must be code-driven and logged.

Required approaches:

- QC-metric outliers using configured robust rules such as MAD/IQR/z-score;
- expression outliers using configured methods such as PCA distance, robust PCA, LOF, or isolation forest;
- candidate outliers separated from final exclusions unless the config allows automatic exclusion;
- every exclusion row must include `sample_id`, `metric_or_method`, `value`, `threshold`, `decision`, and `reason`.

The workflow should produce:

- `results/outlier_audit.csv`
- optional diagnostic plots under `results/qc_plots/`
- method record fields for outlier algorithm, thresholds, and manual approval status.

### Single-cell RNA-seq

The workflow must include a cell-level QC gate before normalization, clustering, marker analysis, integration, or DE.

Required concerns:

- total counts / UMI count per cell;
- detected genes per cell;
- mitochondrial fraction;
- ribosomal fraction where relevant;
- novelty or complexity metrics where relevant;
- ambient RNA handling;
- empty droplets;
- doublet detection;
- expected doublet rate;
- doublet tool and version;
- consensus rule if multiple tools are used;
- tissue-specific or data-driven thresholds.

The workflow should produce:

- `results/cell_qc_audit.csv`
- `results/doublet_audit.csv`
- `results/sc_method.json`
- `results/qc_plots/`

Required method-record fields:

- `cell_qc_metrics`
- `cell_qc_threshold_policy`
- `mitochondrial_gene_definition`
- `mitochondrial_fraction_threshold`
- `doublet_tool`
- `doublet_tool_version`
- `expected_doublet_rate`
- `doublet_threshold`
- `doublet_consensus_rule`
- `ambient_rna_method`
- `de_method`

Single-cell DE should be pseudobulk by sample or donor unless the analysis explicitly justifies another model.

## Proposed Pipeline Contract

The pipeline should move from one dataset-level gate to a layered QC contract:

1. `detect_modality`
2. `dataset_selection_gate`
3. `dataset_audit_approval`
4. `sample_qc_gate`
5. `feature_qc_gate`
6. modality-specific processing:
   - bulk RNA-seq / GTEx;
   - microarray;
   - single-cell;
   - spatial;
   - proteomics;
   - metabolomics / lipidomics.
7. `outlier_gate`
8. `missingness_and_imputation_gate`
9. `differential_expression_or_association`
10. `meta_analysis_or_synthesis`
11. `checksums`
12. `verify`

For interactive runs, the workflow must stop after audit artifacts and require human sign-off. For autonomous runs, the workflow should emit `STATUS=NEEDS_REVIEW` or `STATUS=BLOCKED` instead of continuing through uncertain gates.

## Required Standard Output Files

At minimum, trusted runs should emit:

| File | Purpose |
|---|---|
| `results/modality_detected.csv` | Modality routing and evidence |
| `results/dataset_audit.csv` | Dataset-level include/reject decisions |
| `results/sample_qc_audit.csv` | Bulk/GTEx sample-level QC decisions |
| `results/feature_qc_audit.csv` | Feature-level missingness/zero/low-expression decisions |
| `results/cell_qc_audit.csv` | Single-cell cell-level QC decisions |
| `results/doublet_audit.csv` | Doublet detection decisions |
| `results/outlier_audit.csv` | Sample/cell/expression outlier decisions |
| `results/missingness_audit.csv` | Missingness classification and thresholds |
| `results/imputation_audit.csv` | Imputation decisions and down-weighting policy |
| `results/qc_method.json` | General QC method record |
| `results/sc_method.json` | Single-cell method record |
| `results/run_config_used.json` | Frozen config values used by the run |
| `data/CHECKSUMS.txt` | Checksums for frozen inputs and result tables |
| `results/claim_file_map.csv` | Claim-to-file traceability |

## Verifier Additions Needed

`scripts/verify.py` should fail if:

- text files cannot be read as UTF-8;
- `dataset_audit.csv` has zero rows unless `template_mode: true`;
- any included dataset lacks confirmed modality;
- any included GTEx/bulk sample lacks sample QC rows;
- any included single-cell dataset lacks cell QC rows;
- `0`, `NA`, and `"not applicable"` handling is unspecified;
- imputation is used without an imputation audit;
- outliers are removed without an outlier audit;
- doublets are removed without tool, version, expected rate, threshold, and audit rows;
- mitochondrial fraction filtering is used without gene-set definition and threshold policy;
- final DE/synthesis runs before required audit approval in interactive mode;
- checksum file is missing or mismatched;
- method records do not match `config.yaml`.

## Config Additions Needed

Add a dedicated QC section to `config.yaml`, for example:

```yaml
qc:
  template_mode: false
  require_human_approval_after_dataset_audit: true

  bulk:
    rin:
      policy: "exclude_or_covariate"
      minimum: null
      covariate_allowed: true
    mapping_rate:
      minimum: null
    missingness:
      max_sample_fraction: null
      max_feature_fraction: null
    zero_policy: "distinguish_biological_zero_from_missing"
    not_applicable_policy: "do_not_convert_to_zero"
    outlier:
      methods: ["mad", "pca_distance"]
      automatic_exclusion: false

  single_cell:
    cell_qc_metrics:
      - "total_counts"
      - "detected_genes"
      - "mitochondrial_fraction"
    threshold_policy: "data_driven_documented"
    mitochondrial_gene_definition: null
    doublet:
      tool: null
      expected_rate: null
      consensus_required: false
    ambient_rna:
      method: null
```

The exact thresholds should be dataset- and tissue-specific. If a threshold is missing, the run should block rather than invent a cutoff.

## Source Priority

Use sources in this order:

1. Official project documentation and official pipelines.
2. Peer-reviewed methods papers and package vignettes.
3. Widely used best-practice books or community-maintained methods guides.
4. Tutorials, Q&A posts, videos, and blog posts only as secondary implementation hints.

## Source Library

### GTEx / Bulk RNA-seq

- [GTEx Portal Methods](https://gtexportal.org/home/methods) - official GTEx methods page, including RNA-seq sample exclusion/outlier details.
- [Broad Institute GTEx RNA-seq pipeline](https://github.com/broadinstitute/gtex-pipeline/blob/master/rnaseq/README.md) - alignment, quantification, and quality control pipeline used by GTEx.
- [GTEx/TOPMed pipeline repository](https://github.com/broadinstitute/gtex-pipeline) - broader official pipeline context.
- [GTEx 2017 Nature paper / PubMed](https://pubmed.ncbi.nlm.nih.gov/29022597/) and [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC5776756/) - earlier GTEx resource and analysis reference.
- [GTEx 2020 Science paper / PubMed](https://pubmed.ncbi.nlm.nih.gov/32913098/) and [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC7737656/) - GTEx v8 atlas reference.
- [GTEx_Pro Scientific Reports 2025](https://www.nature.com/articles/s41598-025-20697-0) - useful as a newer reproducible GTEx workflow example, but not the canonical GTEx source.

### Single-cell RNA-seq

- [OSCA release book](https://bioconductor.org/books/release/OSCA/) - Bioconductor single-cell workflows.
- [OSCA quality control chapter](https://bioconductor.org/books/3.12/OSCA/quality-control.html) - cell-level QC metrics and thresholding concepts.
- [OSCA doublet detection chapter](https://bioconductor.org/books/3.12/OSCA/doublet-detection.html) - doublet detection workflow concepts.
- [Single-cell best practices: Quality Control](https://www.sc-best-practices.org/preprocessing_visualization/quality_control.html) - practical QC workflow guidance.
- [Systematic determination of mitochondrial proportion in scRNA-seq QC](https://pmc.ncbi.nlm.nih.gov/articles/PMC8599307/) - tissue-aware mtDNA fraction threshold reference.
- [scDblFinder Bioconductor vignette](https://www.bioconductor.org/packages/release/bioc/vignettes/scDblFinder/inst/doc/scDblFinder.html) and [scDblFinder paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC9204188/) - doublet detection method and implementation reference.
- [10x Genomics single-cell QC filter considerations](https://www.10xgenomics.com/analysis-guides/common-considerations-for-quality-control-filters-for-single-cell-rna-seq-data) - practical vendor guidance; use as secondary support.

### Missingness / Outliers

- Prefer peer-reviewed methods papers, package vignettes, and official workflow documentation.
- Treat blog posts, Q&A, and videos as implementation hints only.
- The previously reviewed MetwareBio and Bioconductor support links can be kept in a "secondary notes" section, but should not be the sole basis for verifier rules.

## Immediate Implementation Plan

1. Choose the canonical source tree.

   Prefer `reproducible-omics/` as the self-contained package and either remove or clearly mark the root files as examples.

2. Fix UTF-8 handling.

   Add explicit `encoding="utf-8"` to Python text reads/writes.

3. Move hardcoded config into `config.yaml`.

   `dataset_selection_gate.py`, `detect_modality.py`, and QC scripts should read one config file.

4. Add approval artifacts.

   Use files such as `results/approvals/dataset_audit_approved.json` and make downstream rules depend on them in interactive mode.

5. Add QC audit scripts.

   Add scripts for sample QC, feature QC, missingness/imputation audit, outlier audit, and single-cell cell QC.

6. Extend verifier.

   Make the terminal gate assert the presence, schema, and method-record consistency of all QC artifacts.

7. Replace weak source citations in the skill.

   Promote GTEx official docs, Broad pipeline, OSCA, sc-best-practices, scDblFinder, and primary papers. Demote blogs/videos/Q&A to secondary notes.

## Expected Final Behavior

A trustworthy GTEx or single-cell run should end in one of these states:

- `STATUS=PASS`: all required metadata, QC artifacts, method records, checksums, and verifier assertions pass.
- `STATUS=NEEDS_REVIEW`: dataset/sample/cell/outlier decisions require human review before downstream analysis.
- `STATUS=BLOCKED`: a required input, threshold, metadata field, source, or verifier condition is missing or inconsistent.

The correct behavior for uncertain QC is not to continue. It is to stop with an auditable reason.

