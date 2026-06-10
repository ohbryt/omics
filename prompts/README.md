# prompts/ — AI Prompt Templates

12 JSON templates for the AI gateway (SPEC §9). Each file: `{id, version, role, system, developer, input_schema, output_schema}`.

| File | id | Role |
|---|---|---|
| 01_planner.json | planner | Modality-specific, approval-gated execution plan |
| 02_code_generation.json | code_generation | Fail-loud worker script generator |
| 03_qc_review.json | qc_review | Advisory sample/cell QC classifier (PASS/REVIEW/FAIL_CANDIDATE) |
| 04_modality_explanation.json | modality_explanation | Explains structural modality detection evidence |
| 05_metadata_gap.json | metadata_gap | Reports missing required metadata fields |
| 06_outlier_explanation.json | outlier_explanation | Explains code-flagged outlier candidates |
| 07_normalization_advice.json | normalization_advice | Advisory normalization method recommendation |
| 08_batch_design_check.json | batch_design_check | Batch/biology confounding assessment |
| 09_integration_strategy.json | integration_strategy | Advisory integration method recommendation |
| 10_missingness_classification.json | missingness_classification | Proposes value_class assignments for missing/zero cells |
| 11_report_draft.json | report_draft | Drafts methods/results prose from method records and audit tables |
| 12_verifier_explanation.json | verifier_explanation | Explains verifier BLOCKED/NEEDS_REVIEW conditions with remediation steps |

## Invariants enforced in every output_schema

Every template's `output_schema` includes these four fields without exception:

- **`input_fields_used`** `(array of strings)` — the model cites every input field it actually read.
- **`missing_metadata`** `(array of strings)` — fields the model needed but could not find; never invented.
- **`status`** `(enum: PASS | NEEDS_REVIEW | BLOCKED)` — uncertain → NEEDS_REVIEW; missing required config → BLOCKED.
- **`warnings`** `(array of strings)` — non-blocking concerns for the human reviewer.

## Behavioural invariants (system/developer text in every template)

- Invent no thresholds — read from config only; null required threshold → BLOCKED.
- Never delete or modify raw data.
- Never silently exclude samples, cells, or features — every exclusion needs an audit row.
- Never collapse the 7 value classes: `biological_zero`, `technical_zero`, `below_lod`, `true_missing`, `unavailable_metadata`, `imputed_placeholder`, `not_applicable`.
- Generated code: validate inputs, explicit UTF-8 I/O, exception handling, capture package versions, write method JSON + audit CSV + run-specific dir, stop on schema mismatch.
- AI is orchestrator and advisor — never the final judge of inclusion/exclusion/outlier/imputation/normalization/interpretation.
