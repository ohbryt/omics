# SPEC.md — AI-Assisted Omics Desktop Application (authoritative)

Status: authoritative source of truth. Version: 1.0. Date: 2026-06-10.

This document is binding. Code, tests, and the verifier are built against it. The
companion `CLAUDE.md` (LLM operating rules) and `QC_REQUIREMENTS_AND_SKILL_REVIEW.md`
(requirements review that motivated this spec) are inputs; where any disagreement
exists, **this file wins**.

---

## 1. Product

A **local-first desktop application** that helps biomedical researchers discover,
download, QC, analyze, and integrate public omics datasets and produce
**reproducible, publication-grade, audited** results.

### 1.1 Defining principle — AI is an orchestrator, never the judge

The AI proposes plans, explains metrics, and **generates code**. It is **never** the
final authority on:

- dataset inclusion / exclusion,
- sample / cell exclusion,
- outlier removal,
- imputation,
- normalization,
- biological interpretation.

Those decisions are **config-driven, executed deterministically by code, logged with
an append-only audit trail, and verified**. Uncertainty stops the pipeline; it does
not get resolved by the model guessing.

### 1.2 Fail-loud at every assay boundary

At every processing boundary the workflow emits exactly one terminal status:

| STATUS | Meaning |
|---|---|
| `PASS` | All required metadata, thresholds, QC artifacts, method records, checksums, and approvals are present and consistent. |
| `NEEDS_REVIEW` | Decisions exist but require human sign-off before downstream analysis (e.g., quarantined accessions, candidate outliers). |
| `BLOCKED` | A required input, threshold, metadata field, artifact, or approval is missing or inconsistent. The run must not continue. |

The correct behavior for uncertainty is **stop with an auditable reason**, never invent
a cutoff or silently proceed.

---

## 2. Architecture (five separated concerns)

```
+------------------+      +-------------------+      +-----------------------+
|  Desktop shell   |<---->|  Backend (FastAPI)|<---->|  Workflow (Snakemake) |
|  React + TS      | HTTP |  typed endpoints  |      |  20 staged rules      |
|  renderer        |      |  AI gateway       |      |  approval-gated DAG   |
|  (NO secrets)    |      |  provenance store |      +-----------+-----------+
+------------------+      +---------+---------+                  |
                                    |                            v
                                    |               +-----------------------+
                                    v               |  Workers (py / R)     |
                          +-------------------+      |  containerised        |
                          |  Vendor APIs      |      |  QC / norm / DE / int |
                          |  OpenAI/Anthropic |      +-----------------------+
                          |  (backend only)   |
                          +-------------------+
```

1. **Desktop shell** (`apps/desktop`): project management, dataset search,
   credential entry (dev), run visualization, human approvals. **No vendor secrets
   ever reach the renderer.**
2. **Backend** (`apps/backend`, FastAPI + Pydantic): typed endpoints, config
   validation, the **AI gateway** (the only component that talks to vendor models),
   and the **provenance store** (SQLite/DuckDB + files).
3. **Workflow** (`workflows/snakemake`): the 20-stage DAG; downstream rules depend on
   approval artifacts.
4. **Workers** (`workers/python`, `workers/r`): the actual download/QC/normalization/
   stats/integration steps, runnable in pinned containers.
5. **Provenance store**: every command, parameter set, container digest, package
   version, prompt, model id, request/response id, generated-code hash, file checksum,
   warning, and decision.

### 2.1 Data-flow invariants

- **Raw data is immutable**: content-addressed cache, never edited in place.
- **Derived data is versioned**: written to run-specific dirs with checksums + manifests.
- **Decisions are append-only**: each row carries `reason`, `metric`, `value`,
  `threshold`, `approver`, `timestamp`.

---

## 3. Missing-value taxonomy (never collapse)

Every numeric/feature cell must be classifiable into exactly one of these, recorded in
schema (column `value_class`), never silently merged:

| Code | Meaning |
|---|---|
| `biological_zero` | True biological absence (e.g., gene genuinely not expressed). |
| `technical_zero` | Zero due to assay/technical dropout. |
| `below_lod` | Below the assay's limit of detection. |
| `true_missing` | Measurement attempted, value absent. |
| `unavailable_metadata` | Metadata field not provided by the source. |
| `imputed_placeholder` | Value filled by imputation; must be flagged + traceable. |
| `not_applicable` | Field/measurement does not apply to this entity. |

Policies (`zero_policy`, `na_policy`, `not_applicable_policy`,
`below_lod_policy`, `imputation_method`, `imputed_value_weighting`) live in
`config.yaml`. A run with unspecified policies **blocks**.

---

## 4. Repository / accession contract

Supported repositories and accession namespaces (modality detection is structural,
not prose-based):

| Repository | Namespace regex | Default modality |
|---|---|---|
| GEO | `^(GSE|GSM)\d+$` | QUERY (E-utilities) |
| SRA | `^(SRR|SRX|SRP|PRJNA)\w+$` | QUERY |
| ArrayExpress/BioStudies | `^E-\w+-\d+$` | QUERY |
| PRIDE/ProteomeXchange | `^PXD\d+$` | proteomics_ms |
| MassIVE | `^MSV\d+$` | proteomics_ms |
| jPOST | `^JPST\d+$` | proteomics_ms |
| MetaboLights | `^MTBLS\d+$` | metabolomics |
| Metabolomics Workbench | `^ST\d+$` | metabolomics |

Modalities: `bulk_transcriptomics`, `single_cell`, `spatial`, `proteomics_ms`,
`affinity_proteomics`, `metabolomics`, `lipidomics`, `unknown`.
`unknown` or low-confidence → **quarantine**, never guessed.

---

## 5. config.yaml sections

`config.yaml` is the single source of truth for all thresholds and policies. **No
threshold may be hardcoded in any script.** Missing required thresholds block the run.

```
project:          # id, name, created_utc, allowed_organisms, required_assay, min_n_total, seed
ai:               # provider, model, prompt_dir, redaction, send_raw_data(false), gateway_log
qc:               # template_mode, require_human_approval_after_dataset_audit
qc.bulk:          # rin, mapping_rate, duplication, mito_fraction, library_size, missingness,
                  #   zero_policy, not_applicable_policy, outlier{methods, automatic_exclusion}
qc.single_cell:   # cell_qc_metrics, threshold_policy, mitochondrial_gene_definition,
                  #   mitochondrial_fraction_threshold, doublet{tool,version,expected_rate,
                  #   threshold,consensus_required}, ambient_rna{method}, de_method(pseudobulk_by_donor)
missingness:      # max_sample_fraction, max_feature_fraction, below_lod_policy,
                  #   imputation{enabled, method, version, target_matrix, downweight}
integration:      # method (combat|combat_seq|harmony|seurat|mofa2), per-view preprocessing,
                  #   require_layers_qc_passed(true)
verifier:         # strict(bool), required_artifacts list, fail_on_empty_audit(true)
fdr:              # method(BH), scope(genome_wide), threshold
paths:            # all result/audit/log/approval paths
```

Threshold fields default to `null`. `null` for a **required** threshold ⇒ `BLOCKED`,
never an invented value.

---

## 6. Core data models (Pydantic v2)

All in `apps/backend/omics_backend/models.py`; JSON Schemas exported to `schemas/`.

- `Project` — id, name, created_utc, root_dir, config snapshot ref.
- `Accession` — id, repository, namespace_valid.
- `MetadataSnapshot` — accession, fetched_utc, source_api, raw fields (verbatim),
  checksum.
- `DatasetAuditRow` — accession, organism_verbatim, platform_GPL, gdstype,
  assay_detected, n_total, n_case, n_control, tissue, decision(INCLUDE/REJECT),
  trigger_field, trigger_value.
- `SampleQCRow` — sample_id, metric, value, threshold, decision, reason, policy.
- `FeatureQCRow` — feature_id, metric, value, threshold, value_class, decision, reason.
- `CellQCRow` — cell_id, sample_id, total_counts, detected_genes, mito_fraction,
  decision, reason.
- `OutlierAuditRow` — entity_id, metric_or_method, value, threshold, decision, reason,
  candidate_only(bool), approved(bool).
- `MissingnessAuditRow` — entity_id, value_class, fraction, threshold, decision.
- `ImputationAuditRow` — target_matrix, method, version, n_imputed, downweighted, reason.
- `ApprovalArtifact` — artifact, approves(path), approver, approved_utc, config_hash,
  decision(APPROVED/REJECTED), note.
- `MethodRecord` — stage, tool, tool_version, package_versions, params, config_hash,
  random_seed, created_utc.
- `RunStatus` — status(PASS/NEEDS_REVIEW/BLOCKED), stage, checks_passed, checks_failed,
  details, created_utc.

Every audit row model carries the append-only provenance quintet where applicable
(`reason`, `metric`/`value`, `threshold`, `approver`, `timestamp`).

---

## 7. The 20 pipeline stages

Each stage declares an **audit-table output** and a **method-record output**.
Downstream rules depend on the relevant **approval artifact**.

| # | Rule | Primary output(s) | Gated by approval |
|---|---|---|---|
| 1 | `detect_modality` | results/modality_detected.csv + method | — |
| 2 | `dataset_selection_gate` | results/dataset_audit.csv + method | — |
| 3 | `dataset_audit_approval` | results/approvals/dataset_audit_approved.json | (produces) |
| 4 | `fetch_raw` | data/raw/<acc>/ (immutable) + data/CHECKSUMS.txt | #3 |
| 5 | `sample_qc_gate` | results/sample_qc_audit.csv + results/qc_method.json | #3 |
| 6 | `feature_qc_gate` | results/feature_qc_audit.csv + method | #3 |
| 7 | `bulk_process` | results/bulk/* + method | #3 |
| 8 | `microarray_process` | results/microarray/* + method | #3 |
| 9 | `single_cell_qc` | results/cell_qc_audit.csv + results/sc_method.json | #3 |
| 10 | `doublet_detection` | results/doublet_audit.csv + method | #3 |
| 11 | `spatial_process` | results/spatial/* + method | #3 |
| 12 | `proteomics_process` | results/proteomics/* + method | #3 |
| 13 | `metabolomics_process` | results/metabolomics/* + method | #3 |
| 14 | `outlier_gate` | results/outlier_audit.csv + method | #3 |
| 15 | `missingness_imputation_gate` | results/missingness_audit.csv, results/imputation_audit.csv + method | #3 |
| 16 | `qc_approval` | results/approvals/qc_approved.json | (produces) |
| 17 | `differential_expression` | results/de/<acc>_de.csv + <acc>_method.json | #16 |
| 18 | `integration` | results/integration/* + method | #16 |
| 19 | `checksums` | data/CHECKSUMS.txt (result tables) | — |
| 20 | `final_verifier` | results/run_status.json (STATUS) | — |

DE (#17) and integration (#18) **must not run** before `qc_approved.json` exists.
Stage #4 (raw fetch) and all QC stages must not run before
`dataset_audit_approved.json` exists.

---

## 8. The 15 verifier failure conditions

`scripts/verify.py` reads **every text file with `encoding="utf-8"`**, emits an
explicit `STATUS=...` line, and exits non-zero on any blocking violation.

1. A text file required for verification cannot be read as UTF-8 → `BLOCKED`.
2. `config.yaml` missing or fails schema validation → `BLOCKED`.
3. `dataset_audit.csv` missing, or has **zero rows** unless `qc.template_mode: true` → `BLOCKED`.
4. Any INCLUDE row whose `organism_verbatim` is not in `project.allowed_organisms` → `BLOCKED`.
5. Any INCLUDE row whose `assay_detected` ≠ `project.required_assay` → `BLOCKED`.
6. Any accession/GPL ID malformed against the namespace regexes → `BLOCKED`.
7. Any INCLUDE row with `n_total < project.min_n_total` → `BLOCKED`.
8. Any INCLUDE dataset lacking a confirmed modality in `modality_detected.csv` → `BLOCKED`.
9. Bulk/GTEx INCLUDE dataset lacking sample-QC rows when sample QC stage ran → `BLOCKED`.
10. Single-cell INCLUDE dataset lacking cell-QC rows; or doublet removal without tool,
    version, expected rate, threshold, and audit rows → `BLOCKED`.
11. Missing-value handling unspecified (no `zero_policy` / `na_policy` /
    `not_applicable_policy`), or imputation used without `imputation_audit.csv` → `BLOCKED`.
12. Outliers excluded without an `outlier_audit.csv` row carrying
    metric/value/threshold/reason → `BLOCKED`.
13. Mitochondrial-fraction filtering used without gene-set definition + threshold policy → `BLOCKED`.
14. DE/integration artifacts present while the required approval artifact is absent;
    or method records do not match `config.yaml`; or FDR not genome-wide → `BLOCKED`.
15. `CHECKSUMS.txt` missing, or any committed checksum mismatches → `BLOCKED`.

Quarantined accessions present (and no blocking failure) → `NEEDS_REVIEW`.
Otherwise → `PASS`.

---

## 9. The 12 AI prompt templates

In `prompts/`, each a JSON file with `{id, version, role, system, developer,
input_schema, output_schema}`. Every output schema **forces**: cite input fields used;
list missing metadata; invent no thresholds; mark uncertain cases `NEEDS_REVIEW`;
generate fail-loud code; never delete raw data; never silently exclude samples; never
collapse `0`/`NA`/`not_applicable`.

1. `planner` — produce a deterministic, modality-specific plan.
2. `code_generation` — generate a fail-loud worker script.
3. `qc_review` — classify samples PASS/REVIEW/FAIL_CANDIDATE (advisory only).
4. `modality_explanation` — explain detected modality from structured evidence.
5. `metadata_gap` — report missing required metadata fields.
6. `outlier_explanation` — explain code-flagged outliers (no exclusion authority).
7. `normalization_advice` — recommend a normalization given config (advisory).
8. `batch_design_check` — check for batch/biology confounding.
9. `integration_strategy` — recommend integration method (advisory).
10. `missingness_classification` — propose value_class mapping for review.
11. `report_draft` — draft methods/results prose from method records + audit tables.
12. `verifier_explanation` — explain a verifier BLOCKED/NEEDS_REVIEW result.

---

## 10. Desktop ↔ backend API contract

Typed REST (OpenAPI auto-generated by FastAPI). All bodies/responses are Pydantic models.

| Method | Path | Purpose |
|---|---|---|
| POST | `/projects` | Create project + generate config.yaml |
| GET | `/projects/{id}` | Project + config snapshot |
| POST | `/projects/{id}/accessions` | Add accession(s) |
| POST | `/projects/{id}/metadata:fetch` | Fetch + store metadata snapshot |
| POST | `/projects/{id}/modality:detect` | Produce modality_detected.csv |
| POST | `/projects/{id}/dataset-audit` | Produce dataset_audit.csv |
| POST | `/projects/{id}/approvals` | Create approval artifact |
| GET | `/projects/{id}/run-status` | Current RunStatus |
| GET | `/projects/{id}/qc-dashboard` | Aggregated QC audit summaries |
| POST | `/ai/code-review` | Submit code/diff for AI review (advisory) |

### 10.1 AI-gateway contract

The gateway is the only path to vendor models. For **every** call it appends a row to
`logs/ai_prompts.jsonl` with: `request_id`, `timestamp_utc`, `model`, `prompt_id`,
`prompt_version`, `provider_request_id`, `provider_response_id`, `input_hash`,
`output_hash`, `redaction_applied`, `generated_code_hash` (if any). Generated code is
also written to `logs/generated_code_manifest.json` (path + sha256 + prompt linkage).

**Secrets**: vendor credentials are read only in the backend process — OS keychain in
dev mode, backend-mediated OAuth/OIDC in production. Never returned to the renderer.
Raw sequence, full matrices, and patient metadata are **never** sent to a model unless
`ai.send_raw_data: true` is explicitly set.

---

## 11. Milestone 1 (this deliverable)

End-to-end, proven:

- config schema + validator;
- project creation (writes `config.yaml`);
- accession metadata-fetch stub (stores a `MetadataSnapshot`);
- modality-detection stub (`results/modality_detected.csv`);
- `results/dataset_audit.csv` generation;
- approval-artifact creation (`results/approvals/dataset_audit_approved.json`);
- `sample_qc_audit.csv` / `outlier_audit.csv` / `missingness_audit.csv` schemas;
- `scripts/verify.py`;
- planner + code-generation prompts;
- generated-code saved, hashed, logged
  (`logs/generated_code_manifest.json`, `logs/ai_prompts.jsonl`);
- test fixtures (one small accession per repo type) + CI for verify.py and config.

### 11.1 Acceptance (fresh-context verifier confirms all)

- A new project can be created and a `config.yaml` is generated.
- An accession can be entered; its metadata is stored as a snapshot.
- `results/modality_detected.csv` and `results/dataset_audit.csv` are produced.
- The workflow **stops** before any downstream analysis until
  `results/approvals/dataset_audit_approved.json` exists.
- `verify.py` blocks empty audit tables, reads all text files as UTF-8, and emits an
  explicit STATUS.
- Generated code is saved, hashed, and logged.
- Fixtures + CI for verify.py and config validation pass.

---

## 12. Definition of done

Monorepo scaffold + Milestone-1 features exist; `scripts/verify.py` runs and prints an
explicit STATUS; the Milestone-1 acceptance checks pass under a **fresh-context
verifier subagent**; CI tests for the verifier and config validation pass. Report the
final STATUS with evidence. If blocked on user-only input (e.g., vendor OAuth
credentials), state exactly what is needed and stop.
