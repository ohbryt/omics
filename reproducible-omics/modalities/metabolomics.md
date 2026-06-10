# Modality: Metabolomics

**Detection signals.** Accession MTBLS (MetaboLights) or ST/Workbench study (Metabolomics Workbench); platform LC-MS, GC-MS, or NMR; targeted vs untargeted. (Confirm via MetaboLights / Workbench API.)

**Selection gates (+ universal organism gate).**
- platform + **ionization/acquisition mode** recorded (LC-MS pos vs neg are separate feature sets; GC-MS; NMR); targeted vs untargeted recorded.
- **annotation / identification confidence level (MSI level 1-4)** recorded; QC samples present (for untargeted drift correction).

**Fixed analysis choices (pin + declare).**
- Peak detection / alignment tool + version + parameters (XCMS / MS-DIAL / MZmine).
- **QC-sample-based drift / batch correction** (LOESS / QC-RLSC) — declare; **missing-value handling**.
- Normalization (PQN / internal standard / median); annotation library + version; ID-confidence threshold for reporting.
- Pos and neg modes processed separately, merged only after annotation with a stated rule.

**Statistics framing.** Per-feature association; BH-FDR across features (per mode, or combined with a stated rule). **Report MSI ID confidence**; putative annotations flagged, not stated as confirmed.

**Biggest non-determinism risks.** Peak-picking/alignment parameters; **drift/batch correction**; annotation tool/library; missing-value handling; ion-mode handling; targeted vs untargeted feature spaces.

**Verifier assertions.** tool + version + parameters recorded; drift correction + QC samples documented; ID-confidence level recorded per reported metabolite; pos/neg handled separately; FDR scope == feature space; targeted not mixed with untargeted.

**Anti-patterns.** Comparing untargeted features across batches without QC-based correction; reporting putative (level 2-3) annotations as confirmed; merging pos/neg or targeted/untargeted without a stated rule.
