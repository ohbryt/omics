/**
 * App.tsx — Multi-view desktop shell for the AI-assisted omics application.
 *
 * Views (navigated via a simple tab bar):
 *   1. ProjectCreate   — create a new project + config.yaml
 *   2. AccessionEntry  — add accession IDs to a project
 *   3. ModalityDetect  — run structural modality detection
 *   4. DatasetAudit    — view dataset_audit.csv rows (INCLUDE / REJECT table)
 *   5. Approval        — HUMAN sign-off before downstream pipeline stages run
 *   6. RunStatus       — PASS (green) / NEEDS_REVIEW (amber) / BLOCKED (red)
 *   7. QcDashboard     — aggregated QC audit summaries
 *
 * SECURITY CONTRACT (SPEC §2, §10.1):
 *   No vendor secrets (API keys, tokens) are ever referenced, stored, or passed
 *   through the renderer. All AI calls go through the backend AI gateway.
 *
 * NOTE ON APPROVALS (SPEC §1.1, §2.1):
 *   The Approval view requires a human-provided approver name and an explicit
 *   APPROVED / REJECTED decision. The application NEVER auto-approves. Downstream
 *   pipeline stages are gated on the presence of the approval artifact.
 */

import { useState, useCallback, type ReactNode } from "react";
import {
  createProject,
  getProject,
  addAccessions,
  fetchMetadata,
  detectModality,
  datasetAudit,
  createApproval,
  getRunStatus,
  getQcDashboard,
  ApiError,
  type Project,
  type DatasetAuditRow,
  type ApprovalArtifact,
  type RunStatus,
  type QcDashboard,
} from "./api/client";
import type { Status } from "./types";

// ---------------------------------------------------------------------------
// Inline styles — no build-time CSS dependency required for the scaffold.
// ---------------------------------------------------------------------------

const s = {
  app: { display: "flex", height: "100vh", flexDirection: "column" as const },
  header: {
    background: "#1a1d2e",
    borderBottom: "1px solid #2d3150",
    padding: "0 1.5rem",
    display: "flex",
    alignItems: "center",
    gap: "0.5rem",
    flexShrink: 0,
  },
  logo: { fontWeight: 700, fontSize: "1rem", color: "#818cf8", marginRight: "1rem" },
  tabBtn: (active: boolean): React.CSSProperties => ({
    padding: "0.75rem 1rem",
    background: "none",
    border: "none",
    borderBottom: active ? "2px solid #818cf8" : "2px solid transparent",
    color: active ? "#e2e8f0" : "#64748b",
    cursor: "pointer",
    fontSize: "0.85rem",
    whiteSpace: "nowrap",
  }),
  content: { flex: 1, overflowY: "auto" as const, padding: "1.5rem" },
  card: {
    background: "#1a1d2e",
    border: "1px solid #2d3150",
    borderRadius: "0.5rem",
    padding: "1.25rem",
    maxWidth: 640,
    marginBottom: "1rem",
  },
  h2: { fontSize: "1rem", fontWeight: 600, marginBottom: "0.75rem", color: "#c7d2fe" },
  label: { display: "block", fontSize: "0.8rem", color: "#94a3b8", marginBottom: "0.25rem" },
  input: {
    width: "100%",
    padding: "0.5rem 0.75rem",
    background: "#0f1117",
    border: "1px solid #2d3150",
    borderRadius: "0.375rem",
    color: "#e2e8f0",
    fontSize: "0.875rem",
    marginBottom: "0.75rem",
  },
  btn: {
    padding: "0.5rem 1.25rem",
    background: "#4f46e5",
    color: "#fff",
    border: "none",
    borderRadius: "0.375rem",
    cursor: "pointer",
    fontSize: "0.875rem",
    fontWeight: 600,
  },
  btnDanger: {
    padding: "0.5rem 1.25rem",
    background: "#dc2626",
    color: "#fff",
    border: "none",
    borderRadius: "0.375rem",
    cursor: "pointer",
    fontSize: "0.875rem",
    fontWeight: 600,
  },
  error: {
    color: "#f87171",
    fontSize: "0.8rem",
    marginTop: "0.5rem",
    background: "#2d1515",
    padding: "0.5rem 0.75rem",
    borderRadius: "0.375rem",
  },
  pre: {
    background: "#0f1117",
    border: "1px solid #2d3150",
    borderRadius: "0.375rem",
    padding: "0.75rem",
    fontSize: "0.78rem",
    color: "#94a3b8",
    overflowX: "auto" as const,
    whiteSpace: "pre-wrap" as const,
  },
  table: { width: "100%", borderCollapse: "collapse" as const, fontSize: "0.8rem" },
  th: {
    textAlign: "left" as const,
    padding: "0.4rem 0.6rem",
    background: "#1e2235",
    color: "#818cf8",
    fontWeight: 600,
    borderBottom: "1px solid #2d3150",
  },
  td: { padding: "0.4rem 0.6rem", borderBottom: "1px solid #1e2235", verticalAlign: "top" as const },
};

// ---------------------------------------------------------------------------
// Status badge helper (SPEC §1.2)
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<Status, string> = {
  PASS: "#16a34a",          // green
  NEEDS_REVIEW: "#d97706",  // amber
  BLOCKED: "#dc2626",       // red
};

function StatusBadge({ status }: { status: Status }): ReactNode {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "0.25rem 0.75rem",
        borderRadius: "9999px",
        background: STATUS_COLORS[status],
        color: "#fff",
        fontWeight: 700,
        fontSize: "0.95rem",
        letterSpacing: "0.05em",
      }}
    >
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function errMsg(e: unknown): string {
  if (e instanceof ApiError) return `API ${e.status}: ${e.detail}`;
  if (e instanceof Error) return e.message;
  return String(e);
}

// ---------------------------------------------------------------------------
// View: ProjectCreate
// ---------------------------------------------------------------------------

function ProjectCreateView({
  onProjectCreated,
}: {
  onProjectCreated: (p: Project) => void;
}): ReactNode {
  const [name, setName] = useState("");
  const [organisms, setOrganisms] = useState("Homo sapiens");
  const [assay, setAssay] = useState("bulk_transcriptomics");
  const [minN, setMinN] = useState("10");
  const [result, setResult] = useState<Project | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = useCallback(async () => {
    if (!name.trim()) { setErr("Project name is required."); return; }
    setLoading(true); setErr("");
    try {
      const p = await createProject({
        name: name.trim(),
        allowed_organisms: organisms.split(",").map((o) => o.trim()).filter(Boolean),
        required_assay: assay.trim() || undefined,
        min_n_total: minN ? parseInt(minN, 10) : undefined,
      });
      setResult(p);
      onProjectCreated(p);
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [name, organisms, assay, minN, onProjectCreated]);

  return (
    <div style={s.card}>
      <h2 style={s.h2}>Create Project</h2>
      <label style={s.label}>Project name</label>
      <input style={s.input} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. adipose_cvd_2026" />
      <label style={s.label}>Allowed organisms (comma-separated)</label>
      <input style={s.input} value={organisms} onChange={(e) => setOrganisms(e.target.value)} />
      <label style={s.label}>Required assay</label>
      <input style={s.input} value={assay} onChange={(e) => setAssay(e.target.value)} />
      <label style={s.label}>Min samples (min_n_total)</label>
      <input style={s.input} type="number" value={minN} onChange={(e) => setMinN(e.target.value)} />
      <button style={s.btn} onClick={submit} disabled={loading}>
        {loading ? "Creating…" : "Create project"}
      </button>
      {err && <div style={s.error}>{err}</div>}
      {result && (
        <pre style={{ ...s.pre, marginTop: "0.75rem" }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// View: AccessionEntry
// ---------------------------------------------------------------------------

function AccessionEntryView({ projectId }: { projectId: string }): ReactNode {
  const [raw, setRaw] = useState("");
  const [result, setResult] = useState<string>("");
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = useCallback(async () => {
    if (!projectId) { setErr("Select or create a project first."); return; }
    const accessions = raw.split(/[\s,]+/).map((a) => a.trim()).filter(Boolean);
    if (!accessions.length) { setErr("Enter at least one accession."); return; }
    setLoading(true); setErr("");
    try {
      const added = await addAccessions(projectId, { accessions });
      setResult(`Added ${added.length} accession(s):\n${added.map((a) => `  ${a.id} (${a.repository})`).join("\n")}`);
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [projectId, raw]);

  const fetchMeta = useCallback(async () => {
    if (!projectId) { setErr("Select or create a project first."); return; }
    setLoading(true); setErr("");
    try {
      const snaps = await fetchMetadata(projectId);
      setResult(`Fetched metadata for ${snaps.length} accession(s).`);
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  return (
    <div style={s.card}>
      <h2 style={s.h2}>Add Accessions</h2>
      {!projectId && <div style={s.error}>No project selected — create one first.</div>}
      <label style={s.label}>Accession IDs (space / comma / newline separated)</label>
      <textarea
        style={{ ...s.input, height: 80, resize: "vertical", fontFamily: "monospace" }}
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        placeholder={"GSE123456\nGSE234567\nPXD001234"}
      />
      <div style={{ display: "flex", gap: "0.5rem" }}>
        <button style={s.btn} onClick={submit} disabled={loading || !projectId}>
          {loading ? "Adding…" : "Add accessions"}
        </button>
        <button style={{ ...s.btn, background: "#0e7490" }} onClick={fetchMeta} disabled={loading || !projectId}>
          {loading ? "Fetching…" : "Fetch metadata"}
        </button>
      </div>
      {err && <div style={s.error}>{err}</div>}
      {result && <pre style={{ ...s.pre, marginTop: "0.75rem" }}>{result}</pre>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// View: ModalityDetect
// ---------------------------------------------------------------------------

function ModalityDetectView({ projectId }: { projectId: string }): ReactNode {
  const [rows, setRows] = useState<Array<{ accession: string; modality: string; confidence: string }>>([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const run = useCallback(async () => {
    if (!projectId) { setErr("Select or create a project first."); return; }
    setLoading(true); setErr("");
    try {
      setRows(await detectModality(projectId));
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  return (
    <div style={s.card}>
      <h2 style={s.h2}>Modality Detection</h2>
      <p style={{ color: "#64748b", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
        Detection is structural (namespace regex) — never prose-based. Uncertain
        accessions are quarantined, never guessed (SPEC §4).
      </p>
      <button style={s.btn} onClick={run} disabled={loading || !projectId}>
        {loading ? "Detecting…" : "Detect modalities"}
      </button>
      {err && <div style={s.error}>{err}</div>}
      {rows.length > 0 && (
        <table style={{ ...s.table, marginTop: "0.75rem" }}>
          <thead>
            <tr>
              <th style={s.th}>Accession</th>
              <th style={s.th}>Modality</th>
              <th style={s.th}>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.accession}>
                <td style={s.td}><code>{r.accession}</code></td>
                <td style={s.td}>{r.modality}</td>
                <td style={{ ...s.td, color: r.modality === "unknown" ? "#f87171" : "#4ade80" }}>
                  {r.confidence}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// View: DatasetAudit
// ---------------------------------------------------------------------------

function DatasetAuditView({ projectId }: { projectId: string }): ReactNode {
  const [rows, setRows] = useState<DatasetAuditRow[]>([]);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const run = useCallback(async () => {
    if (!projectId) { setErr("Select or create a project first."); return; }
    setLoading(true); setErr("");
    try {
      setRows(await datasetAudit(projectId));
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  return (
    <div style={{ ...s.card, maxWidth: "100%" }}>
      <h2 style={s.h2}>Dataset Audit</h2>
      <p style={{ color: "#64748b", fontSize: "0.8rem", marginBottom: "0.75rem" }}>
        Programmatic gates decide INCLUDE / REJECT. Every REJECT names the trigger
        field + value. Human approval is required before downstream analysis (SPEC §1, §6).
      </p>
      <button style={s.btn} onClick={run} disabled={loading || !projectId}>
        {loading ? "Running audit…" : "Run dataset audit"}
      </button>
      {err && <div style={s.error}>{err}</div>}
      {rows.length > 0 && (
        <div style={{ overflowX: "auto", marginTop: "0.75rem" }}>
          <table style={s.table}>
            <thead>
              <tr>
                {["Accession", "Organism", "GPL", "Assay", "N total", "Tissue", "Decision", "Trigger"].map((h) => (
                  <th key={h} style={s.th}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.accession}>
                  <td style={s.td}><code>{r.accession}</code></td>
                  <td style={s.td}>{r.organism_verbatim}</td>
                  <td style={s.td}>{r.platform_gpl ?? "—"}</td>
                  <td style={s.td}>{r.assay_detected ?? "—"}</td>
                  <td style={s.td}>{r.n_total ?? "—"}</td>
                  <td style={s.td}>{r.tissue ?? "—"}</td>
                  <td style={{
                    ...s.td,
                    fontWeight: 700,
                    color: r.decision === "INCLUDE" ? "#4ade80" : "#f87171",
                  }}>
                    {r.decision}
                  </td>
                  <td style={s.td}>
                    {r.trigger_field ? `${r.trigger_field}=${r.trigger_value}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// View: Approval
// ---------------------------------------------------------------------------

function ApprovalView({ projectId }: { projectId: string }): ReactNode {
  const [approves, setApproves] = useState("results/dataset_audit.csv");
  const [approver, setApprover] = useState("");
  const [decision, setDecision] = useState<"APPROVED" | "REJECTED">("APPROVED");
  const [note, setNote] = useState("");
  const [result, setResult] = useState<ApprovalArtifact | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const submit = useCallback(async () => {
    if (!projectId) { setErr("Select or create a project first."); return; }
    if (!approver.trim()) { setErr("Approver name is required."); return; }
    setLoading(true); setErr("");
    try {
      const art = await createApproval(projectId, {
        approves,
        approver: approver.trim(),
        decision,
        note: note.trim() || undefined,
      });
      setResult(art);
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [projectId, approves, approver, decision, note]);

  return (
    <div style={s.card}>
      <h2 style={s.h2}>Human Approval</h2>
      {/*
        IMPORTANT: This is a HUMAN sign-off. The application NEVER auto-approves.
        Downstream pipeline stages (raw fetch, all QC) are gated on the presence
        of the dataset_audit_approved.json artifact (SPEC §7, stage 3).
      */}
      <div style={{
        background: "#1e1a08",
        border: "1px solid #78350f",
        borderRadius: "0.375rem",
        padding: "0.6rem 0.75rem",
        fontSize: "0.8rem",
        color: "#fbbf24",
        marginBottom: "0.75rem",
      }}>
        This action records a HUMAN sign-off. The app never auto-approves.
        Downstream pipeline stages will not run until this artifact exists.
      </div>
      <label style={s.label}>Artifact being approved</label>
      <input style={s.input} value={approves} onChange={(e) => setApproves(e.target.value)} />
      <label style={s.label}>Approver name / ID</label>
      <input style={s.input} value={approver} onChange={(e) => setApprover(e.target.value)} placeholder="Your name or ORCID" />
      <label style={s.label}>Decision</label>
      <select
        style={{ ...s.input, cursor: "pointer" }}
        value={decision}
        onChange={(e) => setDecision(e.target.value as "APPROVED" | "REJECTED")}
      >
        <option value="APPROVED">APPROVED</option>
        <option value="REJECTED">REJECTED</option>
      </select>
      <label style={s.label}>Note (optional)</label>
      <textarea
        style={{ ...s.input, height: 60, resize: "vertical" }}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Reason, caveats, references…"
      />
      <button
        style={decision === "APPROVED" ? s.btn : s.btnDanger}
        onClick={submit}
        disabled={loading || !projectId}
      >
        {loading ? "Submitting…" : `Submit ${decision}`}
      </button>
      {err && <div style={s.error}>{err}</div>}
      {result && (
        <pre style={{ ...s.pre, marginTop: "0.75rem" }}>
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// View: RunStatus
// ---------------------------------------------------------------------------

function RunStatusView({ projectId }: { projectId: string }): ReactNode {
  const [rs, setRs] = useState<RunStatus | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!projectId) { setErr("Select or create a project first."); return; }
    setLoading(true); setErr("");
    try {
      setRs(await getRunStatus(projectId));
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  return (
    <div style={s.card}>
      <h2 style={s.h2}>Run Status</h2>
      <button style={s.btn} onClick={refresh} disabled={loading || !projectId}>
        {loading ? "Refreshing…" : "Refresh status"}
      </button>
      {err && <div style={s.error}>{err}</div>}
      {rs && (
        <div style={{ marginTop: "1rem" }}>
          {/* Status is rendered prominently with green / amber / red (SPEC §1.2) */}
          <div style={{ marginBottom: "0.75rem" }}>
            <StatusBadge status={rs.status} />
          </div>
          <div style={{ color: "#94a3b8", fontSize: "0.8rem", marginBottom: "0.5rem" }}>
            Stage: <strong style={{ color: "#e2e8f0" }}>{rs.stage}</strong>
            &nbsp;&nbsp;Passed: <strong style={{ color: "#4ade80" }}>{rs.checks_passed}</strong>
            &nbsp;&nbsp;Failed: <strong style={{ color: "#f87171" }}>{rs.checks_failed}</strong>
          </div>
          {rs.details.length > 0 && (
            <ul style={{ paddingLeft: "1.25rem", fontSize: "0.8rem", color: "#94a3b8" }}>
              {rs.details.map((d, i) => <li key={i}>{d}</li>)}
            </ul>
          )}
          <div style={{ color: "#475569", fontSize: "0.75rem", marginTop: "0.5rem" }}>
            {rs.created_utc}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// View: QcDashboard
// ---------------------------------------------------------------------------

function QcDashboardView({ projectId }: { projectId: string }): ReactNode {
  const [dash, setDash] = useState<QcDashboard | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!projectId) { setErr("Select or create a project first."); return; }
    setLoading(true); setErr("");
    try {
      setDash(await getQcDashboard(projectId));
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  return (
    <div style={s.card}>
      <h2 style={s.h2}>QC Dashboard</h2>
      <button style={s.btn} onClick={refresh} disabled={loading || !projectId}>
        {loading ? "Loading…" : "Load QC dashboard"}
      </button>
      {err && <div style={s.error}>{err}</div>}
      {dash && (
        <div style={{ marginTop: "0.75rem", fontSize: "0.85rem" }}>
          <Section title="Dataset audit">
            <Kv label="Total" value={dash.dataset_audit_summary.total} />
            <Kv label="Included" value={dash.dataset_audit_summary.included} color="#4ade80" />
            <Kv label="Rejected" value={dash.dataset_audit_summary.rejected} color="#f87171" />
            <Kv label="Quarantined" value={dash.dataset_audit_summary.quarantined} color="#fbbf24" />
          </Section>
          {dash.sample_qc_summary && (
            <Section title="Sample QC">
              <Kv label="Total" value={dash.sample_qc_summary.total} />
              <Kv label="Passed" value={dash.sample_qc_summary.passed} color="#4ade80" />
              <Kv label="Failed" value={dash.sample_qc_summary.failed} color="#f87171" />
            </Section>
          )}
          {dash.outlier_summary && (
            <Section title="Outliers">
              <Kv label="Total flagged" value={dash.outlier_summary.total} />
              <Kv label="Candidate only" value={dash.outlier_summary.candidate_only} />
              <Kv label="Approved exclusions" value={dash.outlier_summary.approved_exclusions} color="#f87171" />
            </Section>
          )}
          {dash.missingness_summary && (
            <Section title="Missing-value classes (SPEC §3)">
              {(Object.entries(dash.missingness_summary.value_class_counts) as [string, number][]).map(
                ([cls, count]) => <Kv key={cls} label={cls} value={count} />,
              )}
            </Section>
          )}
          <Section title="Modalities detected">
            {(Object.entries(dash.modality_summary) as [string, number][]).map(
              ([mod, count]) => <Kv key={mod} label={mod} value={count} />,
            )}
          </Section>
        </div>
      )}
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }): ReactNode {
  return (
    <div style={{ marginBottom: "0.75rem" }}>
      <div style={{ color: "#818cf8", fontWeight: 600, marginBottom: "0.25rem", fontSize: "0.8rem" }}>
        {title}
      </div>
      <div style={{ paddingLeft: "0.75rem" }}>{children}</div>
    </div>
  );
}

function Kv({ label, value, color }: { label: string; value: number; color?: string }): ReactNode {
  return (
    <div style={{ display: "flex", gap: "0.5rem", marginBottom: "0.2rem" }}>
      <span style={{ color: "#64748b", minWidth: 200 }}>{label}</span>
      <span style={{ color: color ?? "#e2e8f0", fontWeight: 600 }}>{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Project selector bar
// ---------------------------------------------------------------------------

function ProjectBar({
  project,
  onLoad,
}: {
  project: Project | null;
  onLoad: (p: Project) => void;
}): ReactNode {
  const [id, setId] = useState("");
  const [err, setErr] = useState("");

  const load = useCallback(async () => {
    if (!id.trim()) return;
    try {
      onLoad(await getProject(id.trim()));
      setErr("");
    } catch (e) {
      setErr(errMsg(e));
    }
  }, [id, onLoad]);

  return (
    <div style={{
      background: "#12152a",
      borderBottom: "1px solid #2d3150",
      padding: "0.5rem 1.5rem",
      display: "flex",
      alignItems: "center",
      gap: "0.75rem",
      fontSize: "0.82rem",
      flexShrink: 0,
    }}>
      <span style={{ color: "#64748b" }}>Project:</span>
      {project ? (
        <span style={{ color: "#818cf8", fontWeight: 600 }}>
          {project.name} <span style={{ color: "#475569" }}>({project.id})</span>
        </span>
      ) : (
        <span style={{ color: "#475569" }}>none selected</span>
      )}
      <input
        style={{ ...s.input, marginBottom: 0, width: 220 }}
        value={id}
        onChange={(e) => setId(e.target.value)}
        placeholder="Load by project ID…"
        onKeyDown={(e) => { if (e.key === "Enter") void load(); }}
      />
      <button style={{ ...s.btn, padding: "0.3rem 0.75rem" }} onClick={load}>Load</button>
      {err && <span style={{ color: "#f87171" }}>{err}</span>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root App
// ---------------------------------------------------------------------------

type Tab =
  | "create"
  | "accessions"
  | "modality"
  | "audit"
  | "approval"
  | "status"
  | "qc";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "create", label: "Create project" },
  { id: "accessions", label: "Accessions" },
  { id: "modality", label: "Modality" },
  { id: "audit", label: "Dataset audit" },
  { id: "approval", label: "Approval" },
  { id: "status", label: "Run status" },
  { id: "qc", label: "QC dashboard" },
];

export default function App(): ReactNode {
  const [tab, setTab] = useState<Tab>("create");
  const [project, setProject] = useState<Project | null>(null);

  const projectId = project?.id ?? "";

  const handleProjectCreated = useCallback((p: Project) => {
    setProject(p);
    setTab("accessions");
  }, []);

  return (
    <div style={s.app}>
      <header style={s.header}>
        <span style={s.logo}>Omics Desktop</span>
        {TABS.map((t) => (
          <button
            key={t.id}
            style={s.tabBtn(tab === t.id)}
            onClick={() => setTab(t.id)}
          >
            {t.label}
          </button>
        ))}
      </header>

      <ProjectBar project={project} onLoad={setProject} />

      <main style={s.content}>
        {tab === "create" && (
          <ProjectCreateView onProjectCreated={handleProjectCreated} />
        )}
        {tab === "accessions" && <AccessionEntryView projectId={projectId} />}
        {tab === "modality" && <ModalityDetectView projectId={projectId} />}
        {tab === "audit" && <DatasetAuditView projectId={projectId} />}
        {tab === "approval" && <ApprovalView projectId={projectId} />}
        {tab === "status" && <RunStatusView projectId={projectId} />}
        {tab === "qc" && <QcDashboardView projectId={projectId} />}
      </main>
    </div>
  );
}
