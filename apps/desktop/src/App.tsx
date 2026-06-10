/**
 * App.tsx — Multi-view desktop shell for the AI-assisted omics application.
 *
 * Views (navigated via a left sidebar):
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
// Design tokens (mirrors CSS custom properties defined in index.html)
// ---------------------------------------------------------------------------

const T = {
  bgBase:      "#0e0f13",
  bgSurface:   "#16181d",
  bgElevated:  "#1c1f27",
  bgHover:     "#20232b",
  border:      "#23262e",
  borderSubtle:"#1c1f24",

  accent:      "#6366f1",
  accentDim:   "#3730a3",
  accentGlow:  "rgba(99,102,241,0.12)",
  accentText:  "#818cf8",

  textPrimary: "#e8eaf0",
  textSecond:  "#8b8fa8",
  textMuted:   "#4a4e62",

  green:       "#22c55e",
  greenDim:    "rgba(34,197,94,0.12)",
  amber:       "#f59e0b",
  amberDim:    "rgba(245,158,11,0.12)",
  red:         "#ef4444",
  redDim:      "rgba(239,68,68,0.12)",

  fontSans:    '"IBM Plex Sans", system-ui, -apple-system, sans-serif',
  fontMono:    '"IBM Plex Mono", "Fira Code", monospace',
  radiusSm:    "6px",
  radiusMd:    "10px",
  radiusLg:    "14px",
  sidebarW:    "236px",
} as const;

// ---------------------------------------------------------------------------
// Shared style builders
// ---------------------------------------------------------------------------

const base: Record<string, React.CSSProperties> = {
  card: {
    background: T.bgSurface,
    border: `1px solid ${T.border}`,
    borderRadius: T.radiusMd,
    padding: "20px 24px",
    maxWidth: 680,
    marginBottom: 16,
  },
  cardWide: {
    background: T.bgSurface,
    border: `1px solid ${T.border}`,
    borderRadius: T.radiusMd,
    padding: "20px 24px",
    marginBottom: 16,
  },
  label: {
    display: "block",
    fontSize: 11,
    fontWeight: 600,
    letterSpacing: "0.06em",
    textTransform: "uppercase" as const,
    color: T.textSecond,
    marginBottom: 6,
    marginTop: 14,
  },
  input: {
    display: "block",
    width: "100%",
    padding: "8px 12px",
    background: T.bgBase,
    border: `1px solid ${T.border}`,
    borderRadius: T.radiusSm,
    color: T.textPrimary,
    fontSize: 13,
    fontFamily: T.fontSans,
    outline: "none",
    transition: "border-color 0.15s",
  },
  textarea: {
    display: "block",
    width: "100%",
    padding: "8px 12px",
    background: T.bgBase,
    border: `1px solid ${T.border}`,
    borderRadius: T.radiusSm,
    color: T.textPrimary,
    fontSize: 12,
    fontFamily: T.fontMono,
    outline: "none",
    resize: "vertical" as const,
    transition: "border-color 0.15s",
  },
  btn: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "7px 16px",
    background: T.accent,
    color: "#fff",
    border: "none",
    borderRadius: T.radiusSm,
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 600,
    fontFamily: T.fontSans,
    letterSpacing: "0.02em",
    transition: "opacity 0.15s",
    whiteSpace: "nowrap" as const,
  },
  btnGhost: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "7px 16px",
    background: T.bgElevated,
    color: T.textPrimary,
    border: `1px solid ${T.border}`,
    borderRadius: T.radiusSm,
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 500,
    fontFamily: T.fontSans,
    transition: "background 0.15s",
    whiteSpace: "nowrap" as const,
  },
  btnDanger: {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "7px 16px",
    background: T.red,
    color: "#fff",
    border: "none",
    borderRadius: T.radiusSm,
    cursor: "pointer",
    fontSize: 12,
    fontWeight: 600,
    fontFamily: T.fontSans,
    letterSpacing: "0.02em",
    transition: "opacity 0.15s",
    whiteSpace: "nowrap" as const,
  },
  error: {
    color: T.red,
    fontSize: 12,
    marginTop: 10,
    background: T.redDim,
    border: `1px solid rgba(239,68,68,0.25)`,
    padding: "8px 12px",
    borderRadius: T.radiusSm,
  },
  pre: {
    background: T.bgBase,
    border: `1px solid ${T.border}`,
    borderRadius: T.radiusSm,
    padding: "12px 14px",
    fontSize: 11,
    fontFamily: T.fontMono,
    color: T.textSecond,
    overflowX: "auto" as const,
    whiteSpace: "pre-wrap" as const,
    lineHeight: 1.6,
    marginTop: 12,
  },
  sectionTitle: {
    fontSize: 13,
    fontWeight: 600,
    color: T.textPrimary,
    marginBottom: 16,
    paddingBottom: 10,
    borderBottom: `1px solid ${T.borderSubtle}`,
  },
  viewDesc: {
    fontSize: 12,
    color: T.textSecond,
    lineHeight: 1.6,
    marginTop: 6,
    marginBottom: 16,
  },
  btnRow: {
    display: "flex",
    gap: 8,
    marginTop: 16,
  },
};

// ---------------------------------------------------------------------------
// Status badge (SPEC §1.2) — PASS=green / NEEDS_REVIEW=amber / BLOCKED=red
// ---------------------------------------------------------------------------

const STATUS_CONFIG: Record<Status, { bg: string; dimBg: string; label: string }> = {
  PASS:         { bg: "#22c55e", dimBg: "rgba(34,197,94,0.12)",    label: "PASS" },
  NEEDS_REVIEW: { bg: "#f59e0b", dimBg: "rgba(245,158,11,0.12)",   label: "NEEDS REVIEW" },
  BLOCKED:      { bg: "#ef4444", dimBg: "rgba(239,68,68,0.12)",    label: "BLOCKED" },
};

function StatusBadge({ status, large }: { status: Status; large?: boolean }): ReactNode {
  const cfg = STATUS_CONFIG[status];
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 6,
        padding: large ? "6px 16px" : "3px 10px",
        borderRadius: 9999,
        background: cfg.dimBg,
        border: `1px solid ${cfg.bg}`,
        color: cfg.bg,
        fontWeight: 700,
        fontSize: large ? 15 : 11,
        letterSpacing: "0.06em",
        fontFamily: T.fontSans,
      }}
    >
      <span
        style={{
          width: large ? 8 : 6,
          height: large ? 8 : 6,
          borderRadius: "50%",
          background: cfg.bg,
          flexShrink: 0,
        }}
      />
      {cfg.label}
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
// Table primitives (sticky header, full-width)
// ---------------------------------------------------------------------------

function AuditTable({ children }: { children: ReactNode }): ReactNode {
  return (
    <div
      style={{
        overflowX: "auto",
        overflowY: "auto",
        maxHeight: 440,
        marginTop: 16,
        borderRadius: T.radiusSm,
        border: `1px solid ${T.border}`,
      }}
    >
      <table
        style={{
          width: "100%",
          borderCollapse: "collapse",
          fontSize: 12,
          fontFamily: T.fontSans,
        }}
      >
        {children}
      </table>
    </div>
  );
}

const thStyle: React.CSSProperties = {
  position: "sticky",
  top: 0,
  textAlign: "left",
  padding: "8px 12px",
  background: T.bgElevated,
  color: T.accentText,
  fontWeight: 600,
  fontSize: 11,
  letterSpacing: "0.05em",
  textTransform: "uppercase",
  borderBottom: `1px solid ${T.border}`,
  whiteSpace: "nowrap",
  zIndex: 1,
};

const tdStyle: React.CSSProperties = {
  padding: "7px 12px",
  borderBottom: `1px solid ${T.borderSubtle}`,
  color: T.textPrimary,
  verticalAlign: "top",
};

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
    <div style={base.card}>
      <div style={base.sectionTitle}>New project</div>
      <p style={base.viewDesc}>
        Initialises a project directory and <code>config.yaml</code>. After creation
        you will be taken to the Accessions view.
      </p>

      <label style={base.label}>Project name</label>
      <input
        style={base.input}
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="e.g. adipose_cvd_2026"
        onKeyDown={(e) => { if (e.key === "Enter") void submit(); }}
      />

      <label style={base.label}>Allowed organisms <span style={{ color: T.textMuted, fontWeight: 400, textTransform: "none" as const }}>(comma-separated)</span></label>
      <input
        style={base.input}
        value={organisms}
        onChange={(e) => setOrganisms(e.target.value)}
        placeholder="Homo sapiens, Mus musculus"
      />

      <label style={base.label}>Required assay</label>
      <input
        style={base.input}
        value={assay}
        onChange={(e) => setAssay(e.target.value)}
        placeholder="bulk_transcriptomics"
      />

      <label style={base.label}>Min samples <span style={{ color: T.textMuted, fontWeight: 400, textTransform: "none" as const }}>(min_n_total)</span></label>
      <input
        style={base.input}
        type="number"
        value={minN}
        onChange={(e) => setMinN(e.target.value)}
      />

      <div style={base.btnRow}>
        <button style={base.btn} onClick={submit} disabled={loading}>
          {loading ? "Creating…" : "Create project"}
        </button>
      </div>

      {err && <div style={base.error}>{err}</div>}
      {result && <pre style={base.pre}>{JSON.stringify(result, null, 2)}</pre>}
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
    <div style={base.card}>
      <div style={base.sectionTitle}>Add accessions</div>
      {!projectId && (
        <div style={{ ...base.error, marginBottom: 16 }}>No project selected — create one first.</div>
      )}
      <p style={base.viewDesc}>
        Paste GEO / SRA / PRIDE accession IDs separated by spaces, commas, or newlines.
      </p>

      <label style={base.label}>Accession IDs</label>
      <textarea
        style={{ ...base.textarea, minHeight: 96 }}
        value={raw}
        onChange={(e) => setRaw(e.target.value)}
        placeholder={"GSE123456\nGSE234567\nPXD001234"}
      />

      <div style={base.btnRow}>
        <button style={base.btn} onClick={submit} disabled={loading || !projectId}>
          {loading ? "Adding…" : "Add accessions"}
        </button>
        <button
          style={{ ...base.btnGhost, color: "#22d3ee" }}
          onClick={fetchMeta}
          disabled={loading || !projectId}
        >
          {loading ? "Fetching…" : "Fetch metadata"}
        </button>
      </div>

      {err && <div style={base.error}>{err}</div>}
      {result && <pre style={base.pre}>{result}</pre>}
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
    <div style={base.card}>
      <div style={base.sectionTitle}>Modality detection</div>
      <p style={base.viewDesc}>
        Detection is structural (namespace regex) — never prose-based. Uncertain
        accessions are quarantined, never guessed (SPEC §4).
      </p>

      <div style={base.btnRow}>
        <button style={base.btn} onClick={run} disabled={loading || !projectId}>
          {loading ? "Detecting…" : "Detect modalities"}
        </button>
      </div>

      {err && <div style={base.error}>{err}</div>}

      {rows.length > 0 && (
        <AuditTable>
          <thead>
            <tr>
              <th style={thStyle}>Accession</th>
              <th style={thStyle}>Modality</th>
              <th style={thStyle}>Confidence</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.accession}>
                <td style={tdStyle}><code>{r.accession}</code></td>
                <td style={tdStyle}>{r.modality}</td>
                <td style={{
                  ...tdStyle,
                  color: r.modality === "unknown" ? T.red : T.green,
                  fontWeight: 600,
                }}>
                  {r.confidence}
                </td>
              </tr>
            ))}
          </tbody>
        </AuditTable>
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

  const included = rows.filter((r) => r.decision === "INCLUDE").length;
  const rejected = rows.filter((r) => r.decision === "REJECT").length;

  return (
    <div style={base.cardWide}>
      <div style={base.sectionTitle}>Dataset audit</div>
      <p style={base.viewDesc}>
        Programmatic gates decide INCLUDE / REJECT. Every REJECT names the trigger
        field + value. Human approval is required before downstream analysis (SPEC §1, §6).
      </p>

      <div style={base.btnRow}>
        <button style={base.btn} onClick={run} disabled={loading || !projectId}>
          {loading ? "Running audit…" : "Run dataset audit"}
        </button>
      </div>

      {err && <div style={base.error}>{err}</div>}

      {rows.length > 0 && (
        <>
          {/* Summary strip */}
          <div style={{
            display: "flex",
            gap: 12,
            marginTop: 16,
            padding: "10px 14px",
            background: T.bgElevated,
            borderRadius: T.radiusSm,
            border: `1px solid ${T.border}`,
          }}>
            <StatChip label="Total" value={rows.length} />
            <div style={{ width: 1, background: T.border, flexShrink: 0 }} />
            <StatChip label="Included" value={included} color={T.green} />
            <StatChip label="Rejected" value={rejected} color={T.red} />
          </div>

          <AuditTable>
            <thead>
              <tr>
                {["Accession", "Organism", "GPL", "Assay", "N total", "Tissue", "Decision", "Trigger"].map((h) => (
                  <th key={h} style={thStyle}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.accession}>
                  <td style={tdStyle}><code>{r.accession}</code></td>
                  <td style={{ ...tdStyle, color: T.textSecond }}>{r.organism_verbatim}</td>
                  <td style={{ ...tdStyle, color: T.textSecond }}>{r.platform_gpl ?? "—"}</td>
                  <td style={{ ...tdStyle, color: T.textSecond }}>{r.assay_detected ?? "—"}</td>
                  <td style={{ ...tdStyle, color: T.textSecond }}>{r.n_total ?? "—"}</td>
                  <td style={{ ...tdStyle, color: T.textSecond }}>{r.tissue ?? "—"}</td>
                  <td style={{ ...tdStyle }}>
                    <span style={{
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 5,
                      padding: "2px 9px",
                      borderRadius: 9999,
                      fontSize: 11,
                      fontWeight: 700,
                      letterSpacing: "0.05em",
                      background: r.decision === "INCLUDE" ? T.greenDim : T.redDim,
                      color: r.decision === "INCLUDE" ? T.green : T.red,
                      border: `1px solid ${r.decision === "INCLUDE" ? "rgba(34,197,94,0.3)" : "rgba(239,68,68,0.3)"}`,
                    }}>
                      {r.decision}
                    </span>
                  </td>
                  <td style={{ ...tdStyle, color: T.textSecond, fontFamily: T.fontMono, fontSize: 11 }}>
                    {r.trigger_field ? `${r.trigger_field}=${r.trigger_value}` : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </AuditTable>
        </>
      )}
    </div>
  );
}

function StatChip({ label, value, color }: { label: string; value: number; color?: string }): ReactNode {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
      <span style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: T.textMuted }}>
        {label}
      </span>
      <span style={{ fontSize: 16, fontWeight: 700, color: color ?? T.textPrimary, lineHeight: 1 }}>
        {value}
      </span>
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
    <div style={base.card}>
      <div style={base.sectionTitle}>Human approval</div>

      {/*
        IMPORTANT: This is a HUMAN sign-off. The application NEVER auto-approves.
        Downstream pipeline stages (raw fetch, all QC) are gated on the presence
        of the dataset_audit_approved.json artifact (SPEC §7, stage 3).
      */}
      <div style={{
        display: "flex",
        gap: 12,
        padding: "12px 14px",
        background: "rgba(245,158,11,0.08)",
        border: "1px solid rgba(245,158,11,0.35)",
        borderRadius: T.radiusSm,
        marginBottom: 16,
      }}>
        <span style={{ fontSize: 16, flexShrink: 0, lineHeight: 1.4 }}>⚠</span>
        <div style={{ fontSize: 12, color: T.amber, lineHeight: 1.6 }}>
          <strong style={{ color: T.amber }}>Human sign-off required.</strong>
          {" "}This application <strong>never auto-approves</strong>. Downstream
          pipeline stages will not execute until this approval artifact is present
          on disk (SPEC §7, stage 3).
        </div>
      </div>

      <label style={base.label}>Artifact being approved</label>
      <input
        style={base.input}
        value={approves}
        onChange={(e) => setApproves(e.target.value)}
      />

      <label style={base.label}>Approver name / ORCID</label>
      <input
        style={base.input}
        value={approver}
        onChange={(e) => setApprover(e.target.value)}
        placeholder="Your name or ORCID iD"
      />

      <label style={base.label}>Decision</label>
      <select
        style={{
          ...base.input,
          cursor: "pointer",
          appearance: "none" as const,
          paddingRight: 32,
          color: decision === "APPROVED" ? T.green : T.red,
          fontWeight: 700,
        }}
        value={decision}
        onChange={(e) => setDecision(e.target.value as "APPROVED" | "REJECTED")}
      >
        <option value="APPROVED">APPROVED</option>
        <option value="REJECTED">REJECTED</option>
      </select>

      <label style={base.label}>Note <span style={{ color: T.textMuted, fontWeight: 400, textTransform: "none" as const }}>(optional)</span></label>
      <textarea
        style={{ ...base.textarea, minHeight: 72 }}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder="Reason, caveats, references…"
      />

      <div style={base.btnRow}>
        <button
          style={decision === "APPROVED" ? base.btn : base.btnDanger}
          onClick={submit}
          disabled={loading || !projectId}
        >
          {loading ? "Submitting…" : `Submit ${decision}`}
        </button>
      </div>

      {err && <div style={base.error}>{err}</div>}
      {result && <pre style={base.pre}>{JSON.stringify(result, null, 2)}</pre>}
    </div>
  );
}

// ---------------------------------------------------------------------------
// View: RunStatus
// ---------------------------------------------------------------------------

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
    <div style={base.card}>
      <div style={base.sectionTitle}>QC dashboard</div>
      <p style={base.viewDesc}>
        Aggregated audit summaries across all pipeline stages.
      </p>

      <div style={base.btnRow}>
        <button style={base.btn} onClick={refresh} disabled={loading || !projectId}>
          {loading ? "Loading…" : "Load QC dashboard"}
        </button>
      </div>

      {err && <div style={base.error}>{err}</div>}

      {dash && (
        <div style={{ marginTop: 16, display: "grid", gap: 12 }}>
          <QcSection title="Dataset audit">
            <QcGrid>
              <QcStat label="Total"       value={dash.dataset_audit_summary.total} />
              <QcStat label="Included"    value={dash.dataset_audit_summary.included}    color={T.green} />
              <QcStat label="Rejected"    value={dash.dataset_audit_summary.rejected}    color={T.red} />
              <QcStat label="Quarantined" value={dash.dataset_audit_summary.quarantined} color={T.amber} />
            </QcGrid>
          </QcSection>

          {dash.sample_qc_summary && (
            <QcSection title="Sample QC">
              <QcGrid>
                <QcStat label="Total"  value={dash.sample_qc_summary.total} />
                <QcStat label="Passed" value={dash.sample_qc_summary.passed} color={T.green} />
                <QcStat label="Failed" value={dash.sample_qc_summary.failed} color={T.red} />
              </QcGrid>
            </QcSection>
          )}

          {dash.outlier_summary && (
            <QcSection title="Outliers">
              <QcGrid>
                <QcStat label="Total flagged"       value={dash.outlier_summary.total} />
                <QcStat label="Candidate only"      value={dash.outlier_summary.candidate_only} />
                <QcStat label="Approved exclusions" value={dash.outlier_summary.approved_exclusions} color={T.red} />
              </QcGrid>
            </QcSection>
          )}

          {dash.missingness_summary && (
            <QcSection title="Missing-value classes (SPEC §3)">
              <div style={{ display: "flex", flexWrap: "wrap" as const, gap: "4px 16px" }}>
                {(Object.entries(dash.missingness_summary.value_class_counts) as [string, number][]).map(
                  ([cls, count]) => (
                    <div key={cls} style={{ display: "flex", gap: 8, fontSize: 12, padding: "3px 0" }}>
                      <span style={{ color: T.textSecond, fontFamily: T.fontMono, fontSize: 11 }}>{cls}</span>
                      <span style={{ color: T.textPrimary, fontWeight: 700 }}>{count}</span>
                    </div>
                  ),
                )}
              </div>
            </QcSection>
          )}

          <QcSection title="Modalities detected">
            <div style={{ display: "flex", flexWrap: "wrap" as const, gap: "4px 16px" }}>
              {(Object.entries(dash.modality_summary) as [string, number][]).map(
                ([mod, count]) => (
                  <div key={mod} style={{ display: "flex", gap: 8, fontSize: 12, padding: "3px 0" }}>
                    <span style={{ color: T.textSecond, fontFamily: T.fontMono, fontSize: 11 }}>{mod}</span>
                    <span style={{ color: T.accentText, fontWeight: 700 }}>{count}</span>
                  </div>
                ),
              )}
            </div>
          </QcSection>
        </div>
      )}
    </div>
  );
}

function QcSection({ title, children }: { title: string; children: ReactNode }): ReactNode {
  return (
    <div style={{
      background: T.bgElevated,
      border: `1px solid ${T.border}`,
      borderRadius: T.radiusSm,
      overflow: "hidden",
    }}>
      <div style={{
        padding: "8px 14px",
        fontSize: 11,
        fontWeight: 600,
        letterSpacing: "0.06em",
        textTransform: "uppercase" as const,
        color: T.accentText,
        borderBottom: `1px solid ${T.border}`,
        background: T.bgSurface,
      }}>
        {title}
      </div>
      <div style={{ padding: "12px 14px" }}>
        {children}
      </div>
    </div>
  );
}

function QcGrid({ children }: { children: ReactNode }): ReactNode {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(120px, 1fr))", gap: 12 }}>
      {children}
    </div>
  );
}

function QcStat({ label, value, color }: { label: string; value: number; color?: string }): ReactNode {
  return (
    <div style={{
      display: "flex",
      flexDirection: "column" as const,
      gap: 3,
      padding: "8px 10px",
      background: T.bgBase,
      borderRadius: T.radiusSm,
      border: `1px solid ${T.borderSubtle}`,
    }}>
      <span style={{ fontSize: 11, color: T.textMuted, fontWeight: 500 }}>{label}</span>
      <span style={{ fontSize: 22, fontWeight: 700, color: color ?? T.textPrimary, lineHeight: 1 }}>{value}</span>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sidebar nav definition
// ---------------------------------------------------------------------------

type Tab =
  | "create"
  | "accessions"
  | "modality"
  | "audit"
  | "approval"
  | "status"
  | "qc";

interface NavItem {
  id: Tab;
  label: string;
  icon: string;
  hint: string;
}

const NAV_ITEMS: NavItem[] = [
  { id: "create",    label: "Create project",  icon: "⊕",  hint: "Initialise a new project" },
  { id: "accessions",label: "Accessions",      icon: "≡",  hint: "Add GEO / SRA / PRIDE IDs" },
  { id: "modality",  label: "Modality",         icon: "◈",  hint: "Structural modality detection" },
  { id: "audit",     label: "Dataset audit",   icon: "⊞",  hint: "INCLUDE / REJECT table" },
  { id: "approval",  label: "Approval",         icon: "✦",  hint: "Human sign-off" },
  { id: "status",    label: "Run status",       icon: "◉",  hint: "PASS / NEEDS_REVIEW / BLOCKED" },
  { id: "qc",        label: "QC dashboard",    icon: "⊠",  hint: "Aggregated QC summaries" },
];

const VIEW_TITLES: Record<Tab, string> = {
  create:     "Create project",
  accessions: "Accessions",
  modality:   "Modality detection",
  audit:      "Dataset audit",
  approval:   "Human approval",
  status:     "Run status",
  qc:         "QC dashboard",
};

// ---------------------------------------------------------------------------
// Sidebar component
// ---------------------------------------------------------------------------

function Sidebar({
  activeTab,
  onTabChange,
  project,
  onLoadProject,
}: {
  activeTab: Tab;
  onTabChange: (t: Tab) => void;
  project: Project | null;
  onLoadProject: (p: Project) => void;
}): ReactNode {
  const [loadId, setLoadId] = useState("");
  const [loadErr, setLoadErr] = useState("");

  const doLoad = useCallback(async () => {
    if (!loadId.trim()) return;
    try {
      onLoadProject(await getProject(loadId.trim()));
      setLoadErr("");
      setLoadId("");
    } catch (e) {
      setLoadErr(errMsg(e));
    }
  }, [loadId, onLoadProject]);

  return (
    <aside
      style={{
        width: T.sidebarW,
        flexShrink: 0,
        background: T.bgSurface,
        borderRight: `1px solid ${T.border}`,
        display: "flex",
        flexDirection: "column",
        height: "100%",
      }}
    >
      {/* Logo / app name */}
      <div style={{
        padding: "18px 16px 14px",
        borderBottom: `1px solid ${T.border}`,
        flexShrink: 0,
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 9,
        }}>
          <div style={{
            width: 28,
            height: 28,
            borderRadius: 8,
            background: `linear-gradient(135deg, ${T.accent} 0%, #8b5cf6 100%)`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 14,
            flexShrink: 0,
          }}>
            ◈
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 13, color: T.textPrimary, letterSpacing: "-0.01em" }}>
              Omics Desktop
            </div>
            <div style={{ fontSize: 10, color: T.textMuted, letterSpacing: "0.03em" }}>
              AI-assisted pipeline
            </div>
          </div>
        </div>
      </div>

      {/* Nav items */}
      <nav style={{ flex: 1, overflowY: "auto", padding: "8px 8px" }}>
        {NAV_ITEMS.map((item) => {
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onTabChange(item.id)}
              title={item.hint}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 9,
                width: "100%",
                padding: "8px 10px",
                background: isActive ? T.accentGlow : "transparent",
                border: isActive ? `1px solid rgba(99,102,241,0.25)` : "1px solid transparent",
                borderRadius: T.radiusSm,
                cursor: "pointer",
                marginBottom: 2,
                textAlign: "left" as const,
                transition: "background 0.12s, border-color 0.12s",
              }}
            >
              <span style={{
                fontSize: 14,
                lineHeight: 1,
                color: isActive ? T.accentText : T.textMuted,
                flexShrink: 0,
                width: 18,
                textAlign: "center" as const,
              }}>
                {item.icon}
              </span>
              <span style={{
                fontSize: 12,
                fontWeight: isActive ? 600 : 400,
                color: isActive ? T.textPrimary : T.textSecond,
                letterSpacing: isActive ? "-0.01em" : "normal",
              }}>
                {item.label}
              </span>
              {/* Approval: special indicator */}
              {item.id === "approval" && (
                <span style={{
                  marginLeft: "auto",
                  fontSize: 9,
                  fontWeight: 700,
                  letterSpacing: "0.05em",
                  color: T.amber,
                  background: T.amberDim,
                  border: "1px solid rgba(245,158,11,0.3)",
                  padding: "1px 5px",
                  borderRadius: 9999,
                }}>
                  HUMAN
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {/* Project context at bottom */}
      <div style={{
        borderTop: `1px solid ${T.border}`,
        padding: "12px 12px",
        flexShrink: 0,
      }}>
        <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase", color: T.textMuted, marginBottom: 8 }}>
          Active project
        </div>
        {project ? (
          <div style={{
            padding: "8px 10px",
            background: T.bgElevated,
            borderRadius: T.radiusSm,
            border: `1px solid ${T.border}`,
            marginBottom: 10,
          }}>
            <div style={{ fontSize: 12, fontWeight: 600, color: T.accentText, marginBottom: 2 }}>
              {project.name}
            </div>
            <div style={{ fontSize: 10, fontFamily: T.fontMono, color: T.textMuted }}>
              {project.id}
            </div>
          </div>
        ) : (
          <div style={{
            padding: "8px 10px",
            background: T.bgBase,
            borderRadius: T.radiusSm,
            border: `1px dashed ${T.border}`,
            marginBottom: 10,
            fontSize: 11,
            color: T.textMuted,
            textAlign: "center" as const,
          }}>
            None selected
          </div>
        )}

        <div style={{ display: "flex", gap: 6 }}>
          <input
            style={{
              ...base.input,
              flex: 1,
              fontSize: 11,
              padding: "6px 8px",
              fontFamily: T.fontMono,
            }}
            value={loadId}
            onChange={(e) => setLoadId(e.target.value)}
            placeholder="Project ID…"
            onKeyDown={(e) => { if (e.key === "Enter") void doLoad(); }}
          />
          <button
            style={{
              ...base.btnGhost,
              padding: "6px 10px",
              fontSize: 11,
            }}
            onClick={doLoad}
          >
            Load
          </button>
        </div>
        {loadErr && <div style={{ ...base.error, marginTop: 6, fontSize: 11 }}>{loadErr}</div>}
      </div>
    </aside>
  );
}

// ---------------------------------------------------------------------------
// Top bar
// ---------------------------------------------------------------------------

function TopBar({
  title,
  project,
  runStatus,
}: {
  title: string;
  project: Project | null;
  runStatus: Status | null;
}): ReactNode {
  return (
    <div style={{
      height: 44,
      borderBottom: `1px solid ${T.border}`,
      display: "flex",
      alignItems: "center",
      padding: "0 24px",
      gap: 14,
      flexShrink: 0,
      background: T.bgBase,
    }}>
      <h1 style={{
        fontSize: 13,
        fontWeight: 600,
        color: T.textPrimary,
        letterSpacing: "-0.01em",
      }}>
        {title}
      </h1>

      {project && (
        <>
          <div style={{ width: 1, height: 16, background: T.border, flexShrink: 0 }} />
          <span style={{ fontSize: 11, color: T.textSecond }}>
            <span style={{ color: T.textMuted }}>Project: </span>
            <span style={{ color: T.accentText, fontWeight: 600 }}>{project.name}</span>
          </span>
        </>
      )}

      {runStatus && (
        <div style={{ marginLeft: "auto" }}>
          <StatusBadge status={runStatus} />
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Root App
// ---------------------------------------------------------------------------

export default function App(): ReactNode {
  const [tab, setTab] = useState<Tab>("create");
  const [project, setProject] = useState<Project | null>(null);
  const [lastRunStatus, setLastRunStatus] = useState<Status | null>(null);

  const projectId = project?.id ?? "";

  const handleProjectCreated = useCallback((p: Project) => {
    setProject(p);
    setTab("accessions");
  }, []);

  // Intercept RunStatus loads to keep the top bar pill in sync
  const handleRunStatusLoad = useCallback((p: Project) => {
    setProject(p);
  }, []);

  return (
    <div style={{
      display: "flex",
      height: "100vh",
      overflow: "hidden",
      background: T.bgBase,
      fontFamily: T.fontSans,
    }}>
      <Sidebar
        activeTab={tab}
        onTabChange={setTab}
        project={project}
        onLoadProject={handleRunStatusLoad}
      />

      <div style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden" }}>
        <TopBar
          title={VIEW_TITLES[tab]}
          project={project}
          runStatus={lastRunStatus}
        />

        <main style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px 28px",
        }}>
          {tab === "create" && (
            <ProjectCreateView onProjectCreated={handleProjectCreated} />
          )}
          {tab === "accessions" && <AccessionEntryView projectId={projectId} />}
          {tab === "modality"   && <ModalityDetectView projectId={projectId} />}
          {tab === "audit"      && <DatasetAuditView   projectId={projectId} />}
          {tab === "approval"   && <ApprovalView        projectId={projectId} />}
          {tab === "status"     && (
            <RunStatusViewWithCallback
              projectId={projectId}
              onStatusLoad={setLastRunStatus}
            />
          )}
          {tab === "qc"         && <QcDashboardView     projectId={projectId} />}
        </main>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// RunStatusViewWithCallback — thin wrapper so the top bar pill updates
// ---------------------------------------------------------------------------

function RunStatusViewWithCallback({
  projectId,
  onStatusLoad,
}: {
  projectId: string;
  onStatusLoad: (s: Status) => void;
}): ReactNode {
  const [rs, setRs] = useState<RunStatus | null>(null);
  const [err, setErr] = useState("");
  const [loading, setLoading] = useState(false);

  const refresh = useCallback(async () => {
    if (!projectId) { setErr("Select or create a project first."); return; }
    setLoading(true); setErr("");
    try {
      const result = await getRunStatus(projectId);
      setRs(result);
      onStatusLoad(result.status);
    } catch (e) {
      setErr(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [projectId, onStatusLoad]);

  return (
    <div style={base.card}>
      <div style={base.sectionTitle}>Run status</div>
      <p style={base.viewDesc}>
        Pipeline gate checks — PASS (green), NEEDS_REVIEW (amber), BLOCKED (red).
      </p>

      <div style={base.btnRow}>
        <button style={base.btn} onClick={refresh} disabled={loading || !projectId}>
          {loading ? "Refreshing…" : "Refresh status"}
        </button>
      </div>

      {err && <div style={base.error}>{err}</div>}

      {rs && (
        <div style={{ marginTop: 20 }}>
          {/* Prominent status (SPEC §1.2) */}
          <div style={{
            display: "flex",
            alignItems: "center",
            gap: 16,
            padding: "16px 20px",
            background: T.bgElevated,
            border: `1px solid ${T.border}`,
            borderRadius: T.radiusMd,
            marginBottom: 16,
          }}>
            <StatusBadge status={rs.status} large />
            <div style={{ fontSize: 12, color: T.textSecond }}>
              Stage: <strong style={{ color: T.textPrimary }}>{rs.stage}</strong>
            </div>
            <div style={{ marginLeft: "auto", display: "flex", gap: 16 }}>
              <div style={{ textAlign: "center" as const }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: T.green, lineHeight: 1 }}>{rs.checks_passed}</div>
                <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" as const, color: T.textMuted, marginTop: 3 }}>passed</div>
              </div>
              <div style={{ textAlign: "center" as const }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: T.red, lineHeight: 1 }}>{rs.checks_failed}</div>
                <div style={{ fontSize: 10, fontWeight: 600, letterSpacing: "0.06em", textTransform: "uppercase" as const, color: T.textMuted, marginTop: 3 }}>failed</div>
              </div>
            </div>
          </div>

          {rs.details.length > 0 && (
            <div style={{
              background: T.bgBase,
              border: `1px solid ${T.border}`,
              borderRadius: T.radiusSm,
              padding: "10px 14px",
            }}>
              {rs.details.map((d, i) => (
                <div key={i} style={{
                  display: "flex",
                  gap: 8,
                  padding: "4px 0",
                  fontSize: 12,
                  color: T.textSecond,
                  borderBottom: i < rs.details.length - 1 ? `1px solid ${T.borderSubtle}` : "none",
                }}>
                  <span style={{ color: T.textMuted, flexShrink: 0 }}>›</span>
                  {d}
                </div>
              ))}
            </div>
          )}

          <div style={{ fontSize: 11, color: T.textMuted, marginTop: 10, fontFamily: T.fontMono }}>
            {rs.created_utc}
          </div>
        </div>
      )}
    </div>
  );
}
