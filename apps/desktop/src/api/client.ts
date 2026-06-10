/**
 * Typed HTTP client for the FastAPI backend (http://127.0.0.1:8765).
 *
 * Covers all 10 endpoints from SPEC §10 exactly — paths are taken verbatim
 * from the spec table and must not diverge from the FastAPI route definitions.
 *
 * SECURITY CONTRACT (SPEC §2, §10.1):
 *   - This file contains NO vendor secrets (no OpenAI/Anthropic keys).
 *   - All AI calls are proxied through the backend's AI gateway; secrets live
 *     only in the backend process (OS keychain in dev, OIDC in prod).
 *   - Raw sequence data and patient metadata are never sent from the renderer.
 */

import type { Decision, ApprovalDecision, Modality, Status, ValueClass } from "../types";

// ---------------------------------------------------------------------------
// Base URL — injected by the preload script via contextBridge, with a fallback
// for browser-only development (e.g., Storybook, unit tests).
// ---------------------------------------------------------------------------

declare global {
  interface Window {
    omicsShell?: { backendBaseUrl: string; platform: string };
  }
}

function getBaseUrl(): string {
  return window.omicsShell?.backendBaseUrl ?? "http://127.0.0.1:8765";
}

// ---------------------------------------------------------------------------
// Shared fetch helper — throws a typed ApiError on non-2xx responses.
// ---------------------------------------------------------------------------

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
  ) {
    super(`API ${status}: ${detail}`);
    this.name = "ApiError";
  }
}

async function request<T>(
  method: "GET" | "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: unknown,
): Promise<T> {
  const url = `${getBaseUrl()}${path}`;
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const err = (await res.json()) as { detail?: string };
      if (err.detail) detail = err.detail;
    } catch {
      // ignore JSON parse failure — keep statusText
    }
    throw new ApiError(res.status, detail);
  }

  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Response models — mirror the Pydantic models in models.py (SPEC §6)
// ---------------------------------------------------------------------------

/** SPEC §6: Project */
export interface Project {
  id: string;
  name: string;
  created_utc: string;
  root_dir: string;
  config_snapshot_ref: string | null;
}

/** SPEC §6: Accession */
export interface Accession {
  id: string;
  repository: string;
  namespace_valid: boolean;
  project_id: string;
}

/** SPEC §6: MetadataSnapshot — verbatim fields from source API + checksum */
export interface MetadataSnapshot {
  accession: string;
  fetched_utc: string;
  source_api: string;
  /** Verbatim key/value pairs as returned by the upstream API. */
  raw_fields: Record<string, string | number | boolean | null>;
  checksum: string;
}

/**
 * SPEC §6: DatasetAuditRow — one row of dataset_audit.csv.
 * decision INCLUDE|REJECT; every REJECT names the trigger field+value.
 */
export interface DatasetAuditRow {
  accession: string;
  organism_verbatim: string;
  platform_gpl: string | null;
  gdstype: string | null;
  assay_detected: string | null;
  n_total: number | null;
  n_case: number | null;
  n_control: number | null;
  tissue: string | null;
  decision: Decision;
  trigger_field: string | null;
  trigger_value: string | null;
}

/** SPEC §6: ApprovalArtifact */
export interface ApprovalArtifact {
  artifact: string;
  approves: string;
  approver: string;
  approved_utc: string;
  config_hash: string;
  decision: ApprovalDecision;
  note: string | null;
}

/**
 * SPEC §6: RunStatus
 * status PASS | NEEDS_REVIEW | BLOCKED — rendered with green/amber/red in the UI.
 */
export interface RunStatus {
  status: Status;
  stage: string;
  checks_passed: number;
  checks_failed: number;
  details: string[];
  created_utc: string;
}

/** Aggregated QC audit summaries returned by GET /projects/{id}/qc-dashboard */
export interface QcDashboard {
  project_id: string;
  dataset_audit_summary: {
    total: number;
    included: number;
    rejected: number;
    quarantined: number;
  };
  sample_qc_summary: {
    total: number;
    passed: number;
    failed: number;
  } | null;
  outlier_summary: {
    total: number;
    candidate_only: number;
    approved_exclusions: number;
  } | null;
  missingness_summary: {
    value_class_counts: Record<ValueClass, number>;
  } | null;
  modality_summary: Record<Modality, number>;
}

/** Response from POST /ai/code-review */
export interface AiCodeReviewResponse {
  request_id: string;
  model: string;
  prompt_id: string;
  /** Advisory findings — the AI never has final authority (SPEC §1.1). */
  findings: Array<{
    severity: "info" | "warning" | "error";
    line: number | null;
    message: string;
  }>;
  generated_code_hash: string | null;
  timestamp_utc: string;
}

// ---------------------------------------------------------------------------
// Request body types
// ---------------------------------------------------------------------------

export interface CreateProjectBody {
  name: string;
  allowed_organisms?: string[];
  required_assay?: string;
  min_n_total?: number;
  seed?: number;
}

export interface AddAccessionsBody {
  accessions: string[];
}

export interface CreateApprovalBody {
  /** Path to the artifact being approved (e.g. results/dataset_audit.csv). */
  approves: string;
  /**
   * Human approver identifier.
   * NOTE: This is a HUMAN sign-off. The app never auto-approves. (SPEC §1.1, §2.1)
   */
  approver: string;
  decision: ApprovalDecision;
  note?: string;
}

export interface AiCodeReviewBody {
  /** The code or diff text to be reviewed (advisory only — SPEC §1.1). */
  code: string;
  context?: string;
}

// ---------------------------------------------------------------------------
// API client functions — one per SPEC §10 endpoint
// ---------------------------------------------------------------------------

/**
 * POST /projects
 * Create a new project and generate its config.yaml (SPEC §10, Milestone-1).
 */
export async function createProject(body: CreateProjectBody): Promise<Project> {
  return request<Project>("POST", "/projects", body);
}

/**
 * GET /projects/{id}
 * Retrieve a project with its config snapshot reference (SPEC §10).
 */
export async function getProject(id: string): Promise<Project> {
  return request<Project>("GET", `/projects/${id}`);
}

/**
 * POST /projects/{id}/accessions
 * Add one or more accessions to an existing project (SPEC §10).
 */
export async function addAccessions(
  projectId: string,
  body: AddAccessionsBody,
): Promise<Accession[]> {
  return request<Accession[]>("POST", `/projects/${projectId}/accessions`, body);
}

/**
 * POST /projects/{id}/metadata:fetch
 * Fetch and store a MetadataSnapshot for each accession in the project (SPEC §10).
 */
export async function fetchMetadata(projectId: string): Promise<MetadataSnapshot[]> {
  return request<MetadataSnapshot[]>("POST", `/projects/${projectId}/metadata:fetch`);
}

/**
 * POST /projects/{id}/modality:detect
 * Produce modality_detected.csv using structural namespace matching (SPEC §10, §4).
 * Returns one entry per accession with detected modality.
 */
export async function detectModality(
  projectId: string,
): Promise<Array<{ accession: string; modality: Modality; confidence: string }>> {
  return request("POST", `/projects/${projectId}/modality:detect`);
}

/**
 * POST /projects/{id}/dataset-audit
 * Run programmatic gates and produce dataset_audit.csv (SPEC §10, §1).
 * Returns one DatasetAuditRow per accession.
 */
export async function datasetAudit(projectId: string): Promise<DatasetAuditRow[]> {
  return request<DatasetAuditRow[]>("POST", `/projects/${projectId}/dataset-audit`);
}

/**
 * POST /projects/{id}/approvals
 * Create a human approval artifact (SPEC §10, §2.1).
 *
 * IMPORTANT: This is a HUMAN sign-off action. The application NEVER auto-approves.
 * The approver field must identify a real person. Downstream pipeline stages are
 * gated on the existence of this artifact (SPEC §7, stages 3, 16).
 */
export async function createApproval(
  projectId: string,
  body: CreateApprovalBody,
): Promise<ApprovalArtifact> {
  return request<ApprovalArtifact>("POST", `/projects/${projectId}/approvals`, body);
}

/**
 * GET /projects/{id}/run-status
 * Retrieve the current RunStatus (PASS | NEEDS_REVIEW | BLOCKED) (SPEC §10, §1.2).
 */
export async function getRunStatus(projectId: string): Promise<RunStatus> {
  return request<RunStatus>("GET", `/projects/${projectId}/run-status`);
}

/**
 * GET /projects/{id}/qc-dashboard
 * Retrieve aggregated QC audit summaries for display in the dashboard (SPEC §10).
 */
export async function getQcDashboard(projectId: string): Promise<QcDashboard> {
  return request<QcDashboard>("GET", `/projects/${projectId}/qc-dashboard`);
}

/**
 * POST /ai/code-review
 * Submit code or a diff to the backend AI gateway for advisory review (SPEC §10).
 *
 * NOTE: The AI gateway is the ONLY path to vendor models. This call never
 * returns or handles vendor secrets in the renderer. Findings are advisory only —
 * the AI is never the final authority on inclusion/exclusion decisions (SPEC §1.1).
 */
export async function aiCodeReview(body: AiCodeReviewBody): Promise<AiCodeReviewResponse> {
  return request<AiCodeReviewResponse>("POST", "/ai/code-review", body);
}
