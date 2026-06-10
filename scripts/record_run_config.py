#!/usr/bin/env python3
"""Freeze the config values that actually governed this run -> results/run_config_used.json.
verify.py compares this against config.yaml to catch silent parameter drift."""
import json, sys
from pathlib import Path
try:
    import yaml
except ImportError:
    sys.exit("PyYAML required (use the pinned environment).")

ROOT = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
used = {
    "required_assay": cfg["required_assay"],
    "fdr_method": cfg["fdr_method"],
    "fdr_scope": cfg["fdr_scope"],
    "fdr_threshold": cfg["fdr_threshold"],
    "normalization": cfg.get("normalization"),
    "probe_collapse_rule": cfg.get("probe_collapse_rule"),
    "pooling": cfg.get("pooling"),
    "seed": cfg.get("seed"),
    "allowed_organisms": cfg["allowed_organisms"],
}
out = ROOT / cfg["paths"]["run_config_used"]
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(used, indent=2))
print("wrote", out.relative_to(ROOT))
