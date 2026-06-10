# Modality: Bulk transcriptomics (RNA-seq / microarray)

**Detection signals.** GEO `gdstype` = "Expression profiling by array" (microarray) or "...by high throughput sequencing" without single-cell/spatial signatures; SRA `library_strategy=RNA-Seq` (bulk). Repositories: GEO, ArrayExpress, SRA, recount3.

**Selection gates (+ universal organism gate).**
- assay ∈ {microarray, rna-seq} and equals `config.required_assay`.
- platform/GPL recorded; n per group ≥ `min_n`; case/control present.

**Fixed analysis choices (pin + declare).**
- Microarray: normalization (RMA) + background correction; **probe→gene collapse rule** (jetset/max-mean) applied identically across datasets; **pinned platform annotation package version**; explicit batch handling.
- RNA-seq: aligner/quantifier + reference genome + versions; DE method fixed (DESeq2 / edgeR / limma-voom); low-count filter stated.
- Cross-dataset: per-dataset **standardized effect + random-effects meta** (report I²); never vote-count; never pool across platforms without harmonization.

**Statistics framing.** Genome-wide Benjamini-Hochberg FDR < 0.05 across all genes. Effect + SE/CI + FDR from the script.

**Biggest non-determinism risks.** Probe-collapse choice; annotation version drift; normalization method; batch/cohort effects; reference/annotation version (RNA-seq).

**Verifier assertions (add to verify.py).** assay == required; probe_collapse_rule == config (microarray); annotation/reference version recorded; FDR genome-wide; no platform mixing in a pooled set; meta used (not vote-counting).

**Anti-patterns.** Mixing microarray + RNA-seq (or different arrays) in one matrix; collapsing probes differently per dataset; counting "X up / Y down".
