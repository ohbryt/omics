/**
 * Shared TypeScript types and enums for the omics desktop app.
 * These mirror the Pydantic models in apps/backend/omics_backend/models.py
 * and the SPEC §3, §4, §6 definitions.
 *
 * IMPORTANT: No vendor secrets are defined here. All AI calls go through the
 * FastAPI backend — the renderer never touches vendor credentials.
 */

// ---------------------------------------------------------------------------
// §1.2 — Terminal run statuses
// ---------------------------------------------------------------------------

/** Terminal status emitted at every pipeline assay boundary (SPEC §1.2). */
export type Status = "PASS" | "NEEDS_REVIEW" | "BLOCKED";

// ---------------------------------------------------------------------------
// §6 — Dataset audit decision
// ---------------------------------------------------------------------------

/** Per-accession inclusion decision written to dataset_audit.csv (SPEC §6). */
export type Decision = "INCLUDE" | "REJECT";

/** Per-approval decision written to the approval artifact (SPEC §6). */
export type ApprovalDecision = "APPROVED" | "REJECTED";

// ---------------------------------------------------------------------------
// §3 — Missing-value taxonomy (never collapse these — SPEC §3)
// ---------------------------------------------------------------------------

/**
 * Every numeric/feature cell must be classified into exactly one of these.
 * Collapsing any two classes is a verifier violation.
 */
export type ValueClass =
  | "biological_zero"    // True biological absence
  | "technical_zero"     // Zero due to assay/technical dropout
  | "below_lod"          // Below assay's limit of detection
  | "true_missing"       // Measurement attempted, value absent
  | "unavailable_metadata" // Metadata field not provided by source
  | "imputed_placeholder"  // Filled by imputation; must be flagged + traceable
  | "not_applicable";    // Field/measurement does not apply to this entity

// ---------------------------------------------------------------------------
// §4 — Modality
// ---------------------------------------------------------------------------

/** Confirmed modality for an accession (SPEC §4). "unknown" → quarantine. */
export type Modality =
  | "bulk_transcriptomics"
  | "single_cell"
  | "spatial"
  | "proteomics_ms"
  | "affinity_proteomics"
  | "metabolomics"
  | "lipidomics"
  | "unknown"; // Low-confidence → quarantine, never guessed (SPEC §4)
