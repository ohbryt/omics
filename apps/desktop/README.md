# apps/desktop — Omics Desktop Shell

Electron + React + TypeScript UI for the AI-assisted omics pipeline.

## Architecture

```
Renderer (React/TS)  --HTTP-->  Backend (FastAPI :8765)  -->  Vendor APIs
     |                                   |
  preload.ts                     AI gateway only
 (contextBridge)              (vendor secrets here only)
```

- **NO secrets in renderer or main process.** Vendor API keys (OpenAI, Anthropic) live
  exclusively in the FastAPI backend — read from the OS keychain (dev) or backend-mediated
  OAuth/OIDC (prod). They are never returned to Electron or the renderer.
- `contextIsolation: true`, `nodeIntegration: false`, `sandbox: true` enforced in main.ts.
- All AI calls are proxied through `POST /ai/code-review` (and other backend endpoints).

## Dev flow

**Prerequisite:** the FastAPI backend must be running on `http://127.0.0.1:8765`.

```bash
# 1. Install deps (from this directory)
npm install

# 2. Type-check only (no build, no network)
npm run typecheck

# 3. Start renderer dev server (Vite HMR on :5173)
npm run dev

# 4. In a second terminal, launch Electron against the dev server
npx electron .
```

## API surface (SPEC §10 — all 10 endpoints)

| Function | Method + Path |
|---|---|
| `createProject` | POST `/projects` |
| `getProject` | GET `/projects/{id}` |
| `addAccessions` | POST `/projects/{id}/accessions` |
| `fetchMetadata` | POST `/projects/{id}/metadata:fetch` |
| `detectModality` | POST `/projects/{id}/modality:detect` |
| `datasetAudit` | POST `/projects/{id}/dataset-audit` |
| `createApproval` | POST `/projects/{id}/approvals` |
| `getRunStatus` | GET `/projects/{id}/run-status` |
| `getQcDashboard` | GET `/projects/{id}/qc-dashboard` |
| `aiCodeReview` | POST `/ai/code-review` |
