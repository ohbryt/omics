# Snakemake Workflow — AI-Assisted Omics Pipeline

## Running the workflow

Always invoke from the **repo root** so `configfile: "config.yaml"` resolves correctly:

```bash
# Dry-run (show DAG without executing)
snakemake -s workflows/snakemake/Snakefile --cores 1 -n

# Full run
snakemake -s workflows/snakemake/Snakefile --cores <N>

# Visualise the DAG
snakemake -s workflows/snakemake/Snakefile --dag | dot -Tpng > dag.png
```

## Approval gating model

The 20-stage DAG enforces two hard human-approval gates via file dependencies.
Snakemake will not schedule any gated rule until the artifact exists on disk.

### Gate 1 — dataset audit approval (`results/approvals/dataset_audit_approved.json`)

Produced by **stage 3** (`dataset_audit_approval`).
Blocks **stages 4–15**:
`fetch_raw`, `sample_qc_gate`, `feature_qc_gate`, `bulk_process`,
`microarray_process`, `single_cell_qc`, `doublet_detection`,
`spatial_process`, `proteomics_process`, `metabolomics_process`,
`outlier_gate`, `missingness_imputation_gate`.

### Gate 2 — QC approval (`results/approvals/qc_approved.json`)

Produced by **stage 16** (`qc_approval`).
Blocks **stages 17–18**: `differential_expression`, `integration`.

## Interactive vs autonomous operation

- **Interactive**: the pipeline stops automatically at each gate. A researcher
  reviews the audit CSV (e.g., `results/dataset_audit.csv`), then creates the
  approval artifact via the FastAPI backend (`POST /projects/{id}/approvals`)
  or writes it manually. Re-running Snakemake then proceeds.

- **Autonomous**: pre-create approval artifacts before invoking Snakemake
  (e.g., in CI with a known-good fixture). The DAG resolves without pausing.

## Terminal target

`rule all` targets `results/run_status.json` written by **stage 20**
(`final_verifier` → `scripts/verify.py`). The verifier exits non-zero on
`STATUS=BLOCKED`, failing the Snakemake run loudly. See SPEC.md §8 for the
15 verifier failure conditions.
