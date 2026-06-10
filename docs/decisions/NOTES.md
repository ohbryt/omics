# Decision log

One decision/lesson per entry. Newest on top. The "why" matters more than the "what".

## 2026-06-10 — Verifier conditions 9/10/13 fire only when the stage *ran*
SPEC §8 c9/c10/c13 are about "present-but-wrong" QC artifacts, not "not-yet-run".
A selection-only Milestone-1 run (valid audit, approval pending) must reach PASS;
downstream gating is enforced by the Snakemake DAG's approval-artifact dependency, not
by the verifier forcing NEEDS_REVIEW. Early code over-flagged absent QC and broke the
valid-audit acceptance.

## 2026-06-10 — `docs/SPEC.md` authored from QC_REQUIREMENTS review + goal structure
The goal named `docs/SPEC.md` as authoritative but it did not exist; the repo's
`QC_REQUIREMENTS_AND_SKILL_REVIEW.md` was the de-facto requirements note. Consolidated
it plus the goal's structural asks (20 stages, config sections, 15 verifier conditions,
12 prompts, API + gateway contracts, 7-class missing taxonomy) into `docs/SPEC.md` and
treat that as the single source of truth.

## 2026-06-10 — Checksums split: raw vs result tables
SPEC §7 listed stage 19 checksums → `data/CHECKSUMS.txt`. The Snakefile splits raw-input
checksums (`data/CHECKSUMS.txt`, written by `fetch_raw`) from result-table checksums
(`results/CHECKSUMS.txt`, written by `checksums`) to avoid two rules declaring the same
output. verify.py condition 15 checks whichever exist and only *requires* them once
DE/integration artifacts are present.

## 2026-06-10 — AI gateway stub mode records the full provenance contract
Without vendor credentials the gateway does not call a model, but it STILL writes the
`ai_prompts.jsonl` row and `generated_code_manifest.json` entry (mode="stub", provider
ids null). This satisfies the Milestone-1 "generated code saved+hashed+logged" acceptance
without credentials, and the live path only needs creds added to the backend.

## 2026-06-10 — Offline-deterministic services for CI
`fetch_metadata` accepts injected metadata so CI never hits NCBI/EBI. Fixtures provide
one accession per repository type with structured fields; live runs pass `online=True`
(future) to query repository APIs. Keeps the acceptance + CI fully reproducible.

## 2026-06-10 — config.yaml rewritten to the SPEC §5 sectioned schema
The legacy flat `config.yaml` (allowed_organisms/required_assay/...) was replaced by the
sectioned schema (project/ai/qc/missingness/integration/fdr/verifier/paths) validated by
`OmicsConfig`. Required thresholds default to `null` and BLOCK at verify time rather than
being given invented defaults.
