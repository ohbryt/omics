# Modality: Single-cell (scRNA-seq / snRNA-seq)

**Detection signals.** Platform/instrument 10x Chromium, Smart-seq, Drop-seq, inDrop, CEL-seq; supplementary files `barcodes.tsv` + `matrix.mtx` (+ features/genes); keywords single cell/single-nucleus/scRNA/snRNA. Repositories: GEO/SRA, CELLxGENE, Human Cell Atlas, Single Cell Portal.

**Selection gates (+ universal organism gate).**
- assay = scRNA/snRNA; **chemistry + Cell Ranger (or STARsolo) version + reference build recorded**.
- min cells per sample and **min biological samples per group** (not cells — see DE rule).

**Fixed analysis choices (pin + declare).**
- Cell QC thresholds: min genes/cell, max % mito, min counts (in config).
- **Doublet removal** (scrublet/DoubletFinder) + parameters; **ambient-RNA correction** (SoupX/CellBender).
- Normalization (lognorm or SCT); HVG selection; **integration/batch method (Harmony / scVI) — scVI is stochastic: pin version + seed**.
- Clustering (**Leiden resolution + seed**) and **UMAP seed**.
- **Cell-type annotation: method + frozen reference + version** (the single biggest reproducibility hole — do not annotate by eyeballing markers).
- **DE = pseudobulk per sample** (aggregate counts per cell-type×sample, then DESeq2/edgeR) — NOT cell-level tests (pseudoreplication inflates significance).

**Statistics framing.** Pseudobulk DE: genome-wide BH-FDR < 0.05. Cluster markers reported separately and labeled as descriptive.

**Biggest non-determinism risks.** Clustering/UMAP/integration stochasticity (seed + tool version); **cell-type annotation** (reference + method); Cell Ranger/reference version; doublet/ambient choices; QC thresholds.

**Verifier assertions.** seeds recorded for clustering/UMAP/integration; integration tool+version pinned; annotation reference frozen + versioned; DE is pseudobulk (sample-level); QC thresholds == config; Cell Ranger/reference version recorded.

**Anti-patterns.** Cell-level DE with n = number of cells (pseudoreplication); annotating clusters from marker genes by eye without a frozen reference; re-running clustering without a fixed seed/resolution; mixing chemistries/references without integration.
