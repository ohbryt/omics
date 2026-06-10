"""Provenance helpers — append-only logs, checksums, hashing (SPEC 2.1, 10.1).

All writes are UTF-8. The AI-prompt log and generated-code manifest are append-only.
Stdlib only.
"""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str = "req") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def append_jsonl(path: str | Path, record: dict) -> None:
    """Append one JSON record as a line (UTF-8), creating parents as needed."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def append_manifest(path: str | Path, entry: dict) -> None:
    """Append an entry to a JSON-array manifest file (UTF-8). Read-modify-write."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    data: list[dict] = []
    if p.exists():
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            if not isinstance(data, list):
                data = []
        except json.JSONDecodeError:
            data = []
    data.append(entry)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_checksums(checksums_path: str | Path, files: list[str | Path], root: str | Path) -> None:
    """Write `sha256  relpath` lines (UTF-8) for the given files."""
    root = Path(root)
    lines = []
    for f in files:
        fp = Path(f)
        rel = fp.relative_to(root) if fp.is_absolute() else fp
        lines.append(f"{sha256_file(root / rel)}  {rel.as_posix()}")
    p = Path(checksums_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
