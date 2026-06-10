# Modality: Spatial transcriptomics

**Detection signals.** Platform 10x Visium / Visium HD, Slide-seq(V2), Stereo-seq (sequencing-based) OR MERFISH, Xenium, CosMx, GeoMx (imaging-based, **targeted gene panel**); files `tissue_positions`, spatial coords, image. Repositories: GEO, 10x datasets, Zenodo, BioImage Archive, CELLxGENE (subset).

**Critical sub-classification (record `platform_class`).**
- **Sequencing-based, whole-transcriptome** (Visium/Slide-seq/Stereo-seq): spot/bead captures **multiple cells** → needs deconvolution; feature space = whole transcriptome.
- **Imaging-based, targeted panel** (MERFISH/Xenium/CosMx/GeoMx): single-cell/subcellular but a **fixed gene panel** → feature space is panel-limited and NOT comparable to whole-transcriptome.

**Selection gates (+ universal organism gate).**
- platform + platform_class recorded; resolution (spot/bead vs single-cell/subcellular); **panel identity** (imaging) recorded; min counts/spot.

**Fixed analysis choices (pin + declare).**
- Imaging-based: **cell segmentation method + version + parameters** (Baysor/Cellpose/vendor) — segmentation is the dominant variable; QC (transcripts/cell), registration.
- Sequencing-based: **deconvolution method + reference + version + seed** (cell2location/RCTD/SPOTlight) to estimate cell-type proportions; spot QC, tissue detection.
- Normalization; **spatially-variable-gene** method fixed (Moran's I / SpatialDE / SPARK); domain/neighborhood detection fixed; region DE via pseudobulk.

**Statistics framing.** SVG and region DE at genome-wide (or panel-wide) BH-FDR; report the feature space (panel vs whole-tx) used for FDR.

**Biggest non-determinism risks.** **Segmentation** (imaging); **deconvolution reference + method** (sequencing); image registration; clustering seed; targeted-panel feature space not comparable across platforms.

**Verifier assertions.** platform_class recorded (sequencing vs imaging); segmentation OR deconvolution tool+version+seed pinned; panel/feature space recorded; FDR scope matches feature space; no mixing of imaging-targeted with sequencing-whole-transcriptome in one feature space.

**Anti-patterns.** Treating a Visium spot as one cell; merging Xenium/MERFISH (targeted) with Visium (whole-tx) as a single matrix; comparing panel genes to whole-transcriptome FDR; deconvolution without a frozen reference/seed.
