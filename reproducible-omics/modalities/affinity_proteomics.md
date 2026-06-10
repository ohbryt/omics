# Modality: Affinity proteomics (Olink / SomaScan)

**Detection signals.** Platform = Olink (Proximity Extension Assay, **NPX** units, log2) or SomaScan/SomaLogic (aptamer/SOMAmer, **RFU** units); keywords proximity extension / aptamer. Not MS. Sources: study-specific, GEO (some), UK Biobank-PPP, deCODE.

**Selection gates (+ universal organism gate).**
- platform recorded (**Olink panel + version** vs **SomaScan version**); units recorded (NPX log2 vs RFU); **LOD information** present.
- protein-to-target mapping recorded (note cross-reactivity / aptamer specificity caveats).

**Fixed analysis choices (pin + declare).**
- **Below-LOD handling** (drop / keep / impute at LOD) — declare.
- Normalization: Olink intensity/bridging normalization (plate/bridge controls) or SomaScan hybridization + median + plate-scale normalization; record exactly.
- Panel/version-specific protein set; batch/plate handling.

**Statistics framing.** Per-protein association; BH-FDR across the panel's proteins. Effect on the platform's native scale (NPX or RFU) — do not convert between platforms.

**Biggest non-determinism risks.** LOD handling; bridging/normalization choices; panel/version mapping; cross-reactivity; **NPX (log2) and RFU are not comparable**.

**Verifier assertions.** platform + panel/version recorded; units consistent within an analysis; LOD handling == config; normalization == config; no pooling of Olink NPX with SomaScan RFU or with MS proteomics without an explicit harmonization model.

**Anti-patterns.** Treating NPX and RFU as the same scale; pooling Olink + SomaScan + MS as one feature; ignoring below-LOD values; mixing panel versions without bridging.
