# AGENTS.md — Rules for LLM-Assisted Omics (reproducible, validated)

These rules are binding for any agent (Codex / CLI) working in this repository. The goal is **deterministic, reproducible, auditable** omics analysis. The agent **orchestrates and writes code; it does not compute or judge data in its head.**

## 0. Non-negotiables (read first)

1. **No hand-computed results.** Never state a number you derived by reasoning — fold change, p value, FDR, sample size, dataset count, gene direction, anything. Every number must come from an executed, committed script's output file/stdout, and you must cite that file. If a number is not yet computed, write and run the code; do not estimate.
2. **No eyeballing for inclusion.** Dataset and sample inclusion/exclusion is decided by code against **structured metadata fields**, never by reading an abstract or a title. The LLM may draft the filter logic; the filter executes deterministically and logs every decision.
3. **No fabrication.** Never invent accession numbers (GSE/GSM/SRR), platform IDs (GPL), gene IDs, or statistics. If unknown, query the API. If a query fails, say so and stop — do not guess.
4. **Stop-and-confirm.** After producing the dataset audit table and before running differential expression, STOP and require human sign-off. Do not run the full pipeline end-to-end unsupervised through the selection step.

## 1. Dataset selection = hard programmatic gates

Query metadata via API only (GEOquery/rentrez/Entrez E-utilities; or GEOparse/pysradb in Python). Apply these gates **in code** to structured fields and write `results/dataset_audit.csv`:

- **Organism gate:** include only records where `organism` exactly equals an allowed value in `config.allowed_organisms` (default: `["Homo sapiens", "Mus musculus"]`). Anything else (dog, chicken, rat, etc.) → REJECT automatically. Log the verbatim organism string.
- **Platform/assay gate:** include only the required assay in `config.required_assay` (e.g., RNA-seq via SRA `library_strategy == "RNA-Seq"`, or GEO `technology`/GPL class). If RNA-seq is required, REJECT microarray (and vice versa). Log the platform/GPL and detected technology.
- **Other recorded gates (configurable):** tissue/depot, minimum n per group, case/control availability, human/mouse build.
- **Audit row per accession:** `accession, organism_verbatim, platform_GPL, technology_detected, n_total, n_case, n_control, tissue, decision(INCLUDE/REJECT), trigger_field, trigger_value`. Every REJECT must name the field+value that triggered it.
- **Human sign-off:** a reviewer approves `dataset_audit.csv` before any downstream step. Record the approver and date.

## 2. Determinism and environment

- Pin everything: `renv.lock` (R) or `environment.yml` + `conda-lock` (Python); build/run inside a container (Docker/Singularity) with a fixed image digest.
- Pin **annotation package versions** explicitly (probe-to-gene annotations drift between versions).
- Set and record a random seed (`set.seed(...)`, `numpy.random.seed(...)`) wherever any stochastic step exists.
- One-command, end-to-end pipeline (Snakemake/Nextflow/Make) regenerates **all** outputs from the accession list. Re-running the same commit must produce byte-identical (or checksum-identical) result tables.
- Commit raw matrices (or a frozen, documented intermediate) plus SHA256 checksums under `data/` and `data/CHECKSUMS.txt`.

## 3. Microarray-specific rules (results must reproduce)

If microarray data are used, fix and declare every choice in `config`:
- Normalization method (e.g., RMA) and background correction — fixed, not per-run.
- **Probe-to-gene collapse rule** (e.g., max-mean, or jetset best-probe) — fixed and applied identically across datasets.
- Pinned platform annotation package + version.
- Batch/cohort handling stated explicitly.
- **Never pool across platforms by vote-counting.** Combine only via per-dataset standardized effect sizes + random-effects meta-analysis (report I^2), or present each dataset separately.

## 4. Statistics and reporting

- Define the significance frame once: e.g., genome-wide Benjamini-Hochberg FDR < 0.05 across all features (not a self-serving within-gene-set FDR). Record it in `config`.
- Report effect size + CI/SE + FDR from the script. Direction (up/down) comes from the computed value, not assumption.
- Tissue mRNA/omics is biological context, not validation of a circulating/clinical biomarker — keep that framing explicit (compartment mismatch).

## 5. Verifier (fail loudly)

Maintain `scripts/verify.py` (or `.R`) that asserts, and exits non-zero on any violation:
- every included dataset's organism is in `allowed_organisms`;
- every included dataset's technology matches `required_assay`;
- no accession/GPL/gene ID is missing or malformed;
- FDR was computed genome-wide; probe-collapse rule is the configured one;
- result checksums match the committed values.
Print a PASS/FAIL count. The pipeline is "done" only when verify passes.

## 6. Human checkpoints (in the loop)

- Checkpoint A: approve `dataset_audit.csv` (selection) before DE.
- Checkpoint B: approve DE parameters (normalization, collapse rule, model, FDR) before synthesis.
- Checkpoint C: a bioinformatician re-runs the pipeline or independently re-derives ≥1 dataset and signs off (use the per-finding verification-worksheet pattern).

## 7. What the agent should output for every analysis

- The exact code (committed), the config used, the audit CSV, the result tables with checksums, and a short log mapping each claim to its source file/line. **No claim without a file behind it.**

---

### Why this works
Reproducibility comes from **deterministic code + pinned environment + machine-checkable gates**, reviewed by a human — not from the LLM's prose. The LLM writes reviewable code and audit logs; it never becomes the source of truth for a number or an inclusion decision.
