"""Frozen-friendly entrypoint for the backend.

PyInstaller bundles this module as the backend executable. It dispatches:
  - OMICS_VERIFY=1  -> run scripts/verify.py against OMICS_ROOT and exit with its code
                       (so the packaged app can run the verifier without a Python install)
  - otherwise        -> serve the FastAPI app with uvicorn

In development this is equivalent to `python -m uvicorn omics_backend.app:app`.
"""
from __future__ import annotations

import os
import runpy
import sys
from pathlib import Path


def _verify_script() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS")) / "scripts" / "verify.py"
    return Path(__file__).resolve().parents[3] / "scripts" / "verify.py"


def main() -> None:
    if os.environ.get("OMICS_VERIFY") == "1":
        # Hand off to verify.py (it reads OMICS_ROOT and calls sys.exit()).
        runpy.run_path(str(_verify_script()), run_name="__main__")
        return

    import uvicorn

    from omics_backend.app import app  # absolute: this module runs as the frozen entry

    host = os.environ.get("OMICS_HOST", "127.0.0.1")
    port = int(os.environ.get("OMICS_PORT", "8765"))
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
