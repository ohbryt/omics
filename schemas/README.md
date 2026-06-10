# schemas

Machine-readable JSON Schemas, exported from the backend Pydantic models. These are the
contract the desktop app's TypeScript types mirror.

- `config.schema.json` — the full `config.yaml` schema (SPEC §5).
- `<Model>.schema.json` — one per core model (SPEC §6): Project, Accession,
  MetadataSnapshot, DatasetAuditRow, SampleQCRow, FeatureQCRow, CellQCRow,
  DoubletAuditRow, OutlierAuditRow, MissingnessAuditRow, ImputationAuditRow,
  ApprovalArtifact, MethodRecord, RunStatus.

Regenerate after changing models:

```bash
export PYTHONPATH=apps/backend
python - <<'PY'
import json; from pathlib import Path
from omics_backend import config_model, models
Path('schemas/config.schema.json').write_text(json.dumps(config_model.export_json_schema(), indent=2), encoding='utf-8')
for n in ['Project','Accession','MetadataSnapshot','DatasetAuditRow','SampleQCRow','FeatureQCRow','CellQCRow','DoubletAuditRow','OutlierAuditRow','MissingnessAuditRow','ImputationAuditRow','ApprovalArtifact','MethodRecord','RunStatus']:
    Path(f'schemas/{n}.schema.json').write_text(json.dumps(getattr(models,n).model_json_schema(), indent=2), encoding='utf-8')
PY
```
