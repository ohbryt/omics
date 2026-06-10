#!/usr/bin/env python3
"""Write or verify SHA256 checksums of result tables -> data/CHECKSUMS.txt.
Usage: python scripts/00_checksums.py [write|verify]"""
import hashlib, sys
from pathlib import Path
try:
    import yaml
except ImportError:
    sys.exit("PyYAML required.")

ROOT = Path(__file__).resolve().parents[1]
cfg = yaml.safe_load((ROOT / "config.yaml").read_text())
CKS = ROOT / cfg["paths"]["checksums"]

def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()

def targets():
    files = sorted((ROOT / "results" / "de").glob("*_de.csv"))
    meta = ROOT / cfg["paths"]["meta_out"]
    if meta.exists(): files.append(meta)
    return files

def main(mode="write"):
    files = targets()
    if mode == "write":
        CKS.parent.mkdir(parents=True, exist_ok=True)
        with open(CKS, "w") as f:
            for p in files:
                f.write(f"{sha256(p)}  {p.relative_to(ROOT)}\n")
        print(f"wrote {len(files)} checksums -> {CKS.relative_to(ROOT)}")
    elif mode == "verify":
        bad = 0
        have = {l.split(None,1)[1].strip(): l.split(None,1)[0] for l in CKS.read_text().splitlines() if l.strip()}
        for p in files:
            rel = str(p.relative_to(ROOT))
            if have.get(rel) != sha256(p):
                print("MISMATCH", rel); bad += 1
        print("checksums OK" if bad == 0 else f"{bad} mismatches"); sys.exit(1 if bad else 0)

if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "write")
