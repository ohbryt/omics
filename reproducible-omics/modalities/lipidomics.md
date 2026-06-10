# Modality: Lipidomics (a metabolomics subtype — confirm before applying)

**Detection signals.** MetaboLights/Workbench study with lipid focus; platform LC-MS/MS or shotgun MS; annotation in **LIPID MAPS shorthand**; tools MS-DIAL / LipidSearch / Lipostar. A metabolomics study is lipidomics only if the assay/annotation is lipid-specific — otherwise treat as metabolomics.

**Selection gates (+ universal organism gate).**
- platform + acquisition mode recorded; **lipid ID confidence recorded** (sum composition vs sn-position vs double-bond position — LIPID MAPS level); isomer ambiguity noted.
- internal standards per lipid class present (for quantification).

**Fixed analysis choices (pin + declare).**
- Annotation tool + version + spectral/library version; **ID-confidence threshold and shorthand level** for reporting.
- **Internal-standard normalization per lipid class**; QC-based drift correction; missing-value handling.
- **Class-level aggregation rule fixed** (how species roll up to classes), if used; isomer handling rule.

**Statistics framing.** Per-lipid-species association; BH-FDR across species. Report at the annotated shorthand level; do not over-state structural detail beyond the ID level.

**Biggest non-determinism risks.** Annotation/ID level and tool/library; isomer/double-bond assignment; per-class internal-standard normalization; drift; species-to-class aggregation.

**Verifier assertions.** ID-confidence + LIPID MAPS shorthand level recorded per species; internal standards per class documented; isomer handling stated; class aggregation rule == config (if used); FDR across the stated feature space.

**Anti-patterns.** Reporting sn-position or double-bond specifics beyond the achieved ID level; aggregating species to classes without a fixed rule; ignoring isomer ambiguity; normalizing without class-matched internal standards.
