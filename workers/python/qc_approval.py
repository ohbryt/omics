#!/usr/bin/env python3
"""Stage 16 gate — qc_approval (SPEC §7).

Like dataset_audit_approval, this worker does NOT create the approval; it FAILS LOUD
(STATUS=BLOCKED, non-zero exit) unless a human has approved the QC artifacts via the app
(results/approvals/qc_approved.json). This blocks differential_expression and
integration until QC is signed off.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--sample-qc")
    ap.add_argument("--feature-qc")
    ap.add_argument("--outlier-audit")
    ap.add_argument("--missingness-audit")
    ap.add_argument("--imputation-audit")
    ap.add_argument("--out-approval", required=True)
    args = ap.parse_args()

    approval = Path(args.out_approval)
    if not approval.exists():
        print(
            "STATUS=BLOCKED: QC not yet approved.\n"
            f"  A human reviewer must approve the QC audits and create {approval}\n"
            "  via the desktop app or services.create_approval(...).\n"
            "  Differential expression and integration remain blocked until then.",
            file=sys.stderr,
        )
        return 1
    try:
        art = json.loads(approval.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        print(f"STATUS=BLOCKED: QC approval artifact unreadable: {e}", file=sys.stderr)
        return 1
    if art.get("decision") != "APPROVED" or not str(art.get("approver", "")).strip():
        print("STATUS=BLOCKED: QC approval present but not APPROVED by a named reviewer.",
              file=sys.stderr)
        return 1
    print(f"STATUS=PASS: QC approved by {art['approver']} at {art.get('approved_utc')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
