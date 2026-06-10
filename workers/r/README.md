# workers/r

Containerised R workers invoked by the Snakemake DAG (`workflows/snakemake`) for
R-ecosystem stages (DESeq2 / limma / Seurat / DEP / xcms / MOFA2 / ComBat). Same
non-negotiables as `workers/python`:

- thresholds come from `config.yaml` only;
- validate inputs and stop on schema mismatch;
- explicit UTF-8 I/O; capture `sessionInfo()` / package versions into the method record;
- write method JSON + audit CSV to a run-specific dir;
- never delete raw data; never silently exclude samples; never collapse the 7 value
  classes (SPEC §3); single-cell DE is pseudobulk-by-donor unless config justifies.

Pinned environments via `renv.lock` and a fixed container digest (Docker/Apptainer).
Scaffolded as stubs in Milestone 1.
