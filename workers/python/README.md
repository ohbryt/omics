# workers/python

Containerised Python workers invoked by the Snakemake DAG (`workflows/snakemake`).
Each worker corresponds to a pipeline stage (SPEC §7) and must, per the non-negotiables:

- read all thresholds from `config.yaml` (no hardcoded cutoffs);
- validate inputs and **stop on schema mismatch**;
- read/write text as **UTF-8** explicitly;
- handle exceptions and capture package versions;
- write a method-record JSON + an audit CSV to a **run-specific** output dir;
- never delete raw data; never silently exclude samples; never collapse the 7
  value classes (SPEC §3).

Workers are scaffolded as stubs in Milestone 1; the DAG wiring (inputs/outputs and the
approval-artifact dependencies) is the contract they fill. Generated worker code is
saved, hashed, and logged via the AI gateway (`logs/generated_code_manifest.json`).
