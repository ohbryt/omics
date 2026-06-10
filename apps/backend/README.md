# apps/backend

FastAPI backend for the AI-assisted omics desktop app. The **only** component that
holds vendor credentials and the only path to vendor models (the AI gateway).

## Modules (`omics_backend/`)

| Module | Role |
|---|---|
| `enums.py` | Status, Decision, ValueClass (7-class missing taxonomy), Modality, Repository |
| `namespaces.py` | Accession namespace regexes + structural modality routing (SPEC §4) |
| `models.py` | Core Pydantic v2 models (SPEC §6); JSON Schemas exported to `schemas/` |
| `config_model.py` | `config.yaml` schema + validator (SPEC §5); `python -m omics_backend.config_model config.yaml` |
| `provenance.py` | Append-only logs, checksums, hashing (SPEC §2.1, §10.1) |
| `gateway.py` | AI gateway: redaction + per-call provenance logging; stub mode without creds (SPEC §10.1) |
| `services.py` | Milestone-1 services: project, metadata fetch, modality detect, dataset audit, approval |
| `app.py` | FastAPI app exposing the SPEC §10 endpoints |

## Run

```bash
export PYTHONPATH=apps/backend
uvicorn omics_backend.app:app --host 127.0.0.1 --port 8765
```

Set `OMICS_WORKSPACE` to point the backend at a project workspace (defaults to repo
root). Vendor creds via `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` (backend env / keychain)
— never returned to the renderer. Without creds, the gateway runs in **stub** mode but
still records the full provenance contract.
