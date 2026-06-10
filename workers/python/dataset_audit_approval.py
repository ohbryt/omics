#!/usr/bin/env python3
"""Stage 3 gate — dataset_audit_approval (SPEC §7).

This worker does NOT create the approval. Human sign-off is recorded only via the
desktop app / backend (`services.create_approval`), which writes
results/approvals/dataset_audit_approved.json. This worker FAILS LOUD (STATUS=BLOCKED,
non-zero exit) when that human approval is absent or malformed, which blocks every
downstream Snakemake rule that depends on the approval artifact.

Usage:
  python workers/python/dataset_audit_approval.py --config config.yaml \
      --audit results/dataset_audit.csv --out-approval results/approvals/dataset_audit_approved.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--audit", required=True)
    ap.add_argument("--out-approval", required=True)
    args = ap.parse_args()

    audit = Path(args.audit)
    approval = Path(args.out_approval)

    if not audit.exists():
        print("STATUS=BLOCKED: dataset_audit.csv missing; run the dataset selection gate first.",
              file=sys.stderr)
        return 1

    if not approval.exists():
        print(
            "STATUS=BLOCKED: dataset audit not yet approved.\n"
            f"  A human reviewer must approve {audit} and create {approval}\n"
            "  via the desktop app (Approval view) or services.create_approval(...).\n"
            "  Downstream raw-fetch / QC / DE stages remain blocked until then.",
            file=sys.stderr,
        )
        return 1

    # Validate the human-created approval is well-formed and APPROVED.
    try:
        art = json.loads(approval.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"STATUS=BLOCKED: approval artifact unreadable: {e}", file=sys.stderr)
        return 1

    if art.get("decision") != "APPROVED" or not str(art.get("approver", "")).strip():
        print("STATUS=BLOCKED: approval artifact present but not APPROVED by a named reviewer.",
              file=sys.stderr)
        return 1

    print(f"STATUS=PASS: dataset audit approved by {art['approver']} at {art.get('approved_utc')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
