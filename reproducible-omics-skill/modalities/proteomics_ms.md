# Modality: MS-based proteomics (DDA / DIA)

**Detection signals.** Accession PXD (PRIDE/ProteomeXchange), MSV (MassIVE), JPST (jPOST); instrument = mass spectrometer; files `.raw`/`.mzML`/`.d`/`.mzid`; acquisition DDA or DIA. (Confirm via ProteomeXchange/PRIDE API.)

**Selection gates (+ universal organism gate).**
- **acquisition recorded (DDA vs DIA)** — DIA requires a spectral library; do not mix DDA and DIA.
- instrument + quantification type (label-free LFQ vs TMT/iTRAQ) recorded; **FASTA database + version** recorded.

**Fixed analysis choices (pin + declare).**
- Search engine + version (MaxQuant / FragPipe / DIA-NN / Spectronaut); FASTA + version + contaminants (cRAP); fixed/variable modifications; enzyme/missed cleavages.
- **FDR = target-decoy, 1% at PSM / peptide / protein** (this is NOT genome-wide BH); protein inference / razor-peptide rule; match-between-runs on/off recorded.
- Normalization (median / quantile / VSN); **missing-value handling (MNAR vs MAR; imputation method or none)** — declare explicitly; summarization (MaxLFQ / iBAQ / TMT reporter).
- Differential abundance: limma / MSstats on log-intensities.

**Statistics framing.** Identification FDR via target-decoy (1% stated levels); differential-abundance significance via BH across quantified proteins. Report both.

**Biggest non-determinism risks.** **Missing-value imputation**; normalization; FASTA/search-engine version; match-between-runs; DDA-vs-DIA differences; batch/lab effects.

**Verifier assertions.** search engine + version + FASTA version recorded; FDR is target-decoy at the stated levels; imputation method == config; normalization == config; acquisition not mixed (no DDA+DIA in one quantification); quantification type consistent (no TMT+LFQ pooled).

**Anti-patterns.** Imputing MNAR as MAR silently; pooling across labs without batch handling; mixing TMT and LFQ or DDA and DIA; reporting genome-wide BH instead of target-decoy identification FDR.
