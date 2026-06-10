# tests

Offline, deterministic tests. Run from repo root with the backend on the path:

```bash
export PYTHONPATH=apps/backend
python -m pytest tests/ -q
```

| File | Covers |
|---|---|
| `test_config.py` | config schema validation: valid repo config, missing sections, bad enums, genome-wide FDR, forbidden extra keys |
| `test_verify.py` | verifier: empty/missing audit BLOCKS, valid audit PASSES, organism violation BLOCKS, UTF-8 read of non-ASCII |
| `test_milestone1.py` | end-to-end (SPEC §11.1): project→config, metadata snapshot, modality+audit, approval gate, gateway code logging + redaction |
| `test_api.py` | SPEC §10 endpoints via FastAPI TestClient on an isolated workspace |
| `fixtures/accessions.json` | one small accession per repository type (GEO/SRA/PRIDE/MetaboLights) with injected metadata; mixed INCLUDE/REJECT |

Each test runs in an isolated `tmp_path` workspace (`conftest.py::workspace`) so they
never mutate the repo. The verifier subprocess uses `PYTHONPATH=apps/backend` for strict
schema validation while `ROOT` stays in the temp dir.
