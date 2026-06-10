# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec — freezes the omics backend into a standalone executable.

Build (from repo root or anywhere):
    <venv>/python -m PyInstaller apps/backend/omics-backend.spec --noconfirm

Output: apps/backend/dist/omics-backend/  (onedir; electron-builder ships it as
resources/backend/). The exe serves uvicorn by default, or runs the verifier when
OMICS_VERIFY=1 (see omics_backend/__main__.py).
"""
import os
from PyInstaller.utils.hooks import collect_all

REPO = os.path.abspath(os.path.join(SPECPATH, "..", ".."))  # noqa: F821 (SPECPATH injected)

datas, binaries, hiddenimports = [], [], []
for pkg in ["uvicorn", "fastapi", "starlette", "pydantic", "pydantic_core",
            "yaml", "anyio", "click", "h11", "sniffio", "annotated_types"]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# Bundle the verifier script + prompts so the packaged app can verify + use the gateway.
datas += [(os.path.join(REPO, "scripts", "verify.py"), "scripts")]
datas += [(os.path.join(REPO, "prompts"), "prompts")]

a = Analysis(
    [os.path.join(REPO, "apps", "backend", "omics_backend", "__main__.py")],
    pathex=[os.path.join(REPO, "apps", "backend")],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports + ["omics_backend", "omics_backend.app"],
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="omics-backend",
    console=True,
)
coll = COLLECT(exe, a.binaries, a.datas, name="omics-backend")
