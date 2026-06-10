# AI-Assisted Omics Desktop Application

A local-first desktop app that helps biomedical researchers discover, download, QC,
analyze, and integrate public omics datasets and produce **reproducible,
publication-grade, audited** results.

> **Defining principle:** the AI orchestrates and writes code; it is **never** the
> final judge of dataset inclusion, sample exclusion, outlier removal, imputation,
> normalization, or interpretation. Those are config-driven, executed by code, logged
> append-only, and verified. Uncertainty **stops** the pipeline — it is never resolved
> by the model guessing. See [`docs/SPEC.md`](docs/SPEC.md) (authoritative).

## Monorepo layout

| Path | Purpose |
|---|---|
| `apps/desktop` | Electron + React + TypeScript shell (no vendor secrets in renderer) |
| `apps/backend` | FastAPI backend + AI gateway + provenance + config validation + Milestone-1 services |
| `workflows/snakemake` | The 20-stage, approval-gated analysis DAG |
| `workers/python`, `workers/r` | Containerised QC / normalization / DE / integration workers |
| `prompts` | 12 JSON-schema-constrained AI prompt templates |
| `schemas` | Exported JSON Schemas (config + core models) |
| `scripts/verify.py` | The terminal gate — 15 conditions, emits `STATUS=PASS\|NEEDS_REVIEW\|BLOCKED` |
| `tests` | Config + verifier + Milestone-1 + API tests with offline fixtures |
| `config.yaml` | Single source of truth for thresholds and policies |
| `docs` | `SPEC.md` (authoritative) + `decisions/NOTES.md` |

The legacy single-pipeline skeleton (root `Snakefile`, `dataset_selection_gate.py`,
`detect_modality.py`, `reproducible-omics/`) is retained as reference; the canonical
implementation is the monorepo above.

## Quick start (backend + verifier)

```bash
# from repo root
export PYTHONPATH=apps/backend          # Windows PowerShell: $env:PYTHONPATH="apps/backend"
pip install pydantic pyyaml fastapi "uvicorn[standard]" httpx pytest

python -m omics_backend.config_model config.yaml   # validate config
python -m pytest tests/ -q                          # run the suite
python scripts/verify.py                            # terminal gate (exits non-zero unless PASS)

# run the backend API (SPEC §10 contract)
uvicorn omics_backend.app:app --host 127.0.0.1 --port 8765
```

## The status contract

Every run ends in exactly one terminal status: **PASS**, **NEEDS_REVIEW**, or
**BLOCKED**. An unpopulated or partially populated repo never reports PASS.

## Reproducibility invariants

- Raw data is immutable (content-addressed; never edited in place).
- Derived data is versioned; decisions are append-only (`reason`, `metric`, `value`,
  `threshold`, `approver`, `timestamp`).
- Every result is reproducible from accessions, `config.yaml`, container digests,
  package versions, checksums, prompts, generated-code hashes, and logs.

## Security

Vendor (OpenAI/Anthropic) credentials live **only** in the backend (OS keychain in dev;
backend-mediated OAuth/OIDC in production) and never reach the renderer. Sensitive
metadata is redacted before any prompt; raw sequence / full matrices / patient metadata
are never sent to a model unless `ai.send_raw_data: true` is explicitly set.
