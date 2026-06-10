/**
 * Electron main process — desktop shell for the AI-assisted omics app.
 *
 * Responsibilities:
 *   - Spawn and supervise the FastAPI backend (the ONLY component that holds vendor
 *     credentials), wait until it is healthy, then load the renderer.
 *   - Kill the backend on quit so no orphan process is left behind.
 *
 * SECURITY CONTRACT (SPEC §2, §10.1):
 *   - Vendor API keys NEVER live here or in the renderer. The backend reads them from
 *     the OS keychain / backend env; they are never returned to this process.
 *   - The renderer talks to the backend over local HTTP only (no Node, no ipc secrets).
 */

import { app, BrowserWindow, shell } from "electron";
import { spawn, type ChildProcess } from "node:child_process";
import path from "node:path";
import http from "node:http";

// vite-plugin-electron emits CommonJS, so __dirname is available natively here.
const VITE_DEV_SERVER_URL = process.env["VITE_DEV_SERVER_URL"];

// Repo root in dev = four levels up from apps/desktop/dist-electron/main.js
// (dist-electron/ -> desktop/ -> apps/ -> repo). In a packaged app this is overridden.
const REPO_ROOT = path.resolve(__dirname, "..", "..", "..");
const BACKEND_PORT = 8765;
const BACKEND_HOST = "127.0.0.1";

let backend: ChildProcess | null = null;

function startBackend(): void {
  const workspace =
    process.env["OMICS_WORKSPACE"] ||
    (VITE_DEV_SERVER_URL ? REPO_ROOT : path.join(app.getPath("userData"), "workspace"));

  const baseEnv = {
    ...process.env,
    OMICS_WORKSPACE: workspace,
    OMICS_HOST: BACKEND_HOST,
    OMICS_PORT: String(BACKEND_PORT),
    PYTHONUTF8: "1",
  };

  if (VITE_DEV_SERVER_URL) {
    // Dev: run the backend from source with the project's Python.
    const py = process.env["OMICS_PYTHON"] || "python";
    backend = spawn(
      py,
      ["-m", "uvicorn", "omics_backend.app:app", "--host", BACKEND_HOST, "--port", String(BACKEND_PORT)],
      { cwd: REPO_ROOT, env: { ...baseEnv, PYTHONPATH: path.join(REPO_ROOT, "apps", "backend") }, stdio: "inherit" },
    );
  } else {
    // Packaged: launch the bundled backend executable (PyInstaller), shipped as an
    // extraResource under resources/backend/. No Python required on the host.
    const exe = process.platform === "win32" ? "omics-backend.exe" : "omics-backend";
    const backendExe = path.join(process.resourcesPath, "backend", exe);
    backend = spawn(backendExe, [], { env: baseEnv, stdio: "inherit" });
  }

  backend.on("exit", (code) => {
    // If the backend dies unexpectedly, surface it in the console; the renderer will
    // show connection errors via the API client.
    console.error(`[backend] exited with code ${code}`);
    backend = null;
  });
}

function stopBackend(): void {
  if (backend && !backend.killed) {
    backend.kill();
    backend = null;
  }
}

function waitForBackend(timeoutMs = 30000): Promise<boolean> {
  const deadline = Date.now() + timeoutMs;
  return new Promise((resolve) => {
    const probe = (): void => {
      const req = http.get(
        { host: BACKEND_HOST, port: BACKEND_PORT, path: "/health", timeout: 1500 },
        (res) => {
          res.resume();
          if (res.statusCode === 200) resolve(true);
          else retry();
        },
      );
      req.on("error", retry);
      req.on("timeout", () => {
        req.destroy();
        retry();
      });
    };
    const retry = (): void => {
      if (Date.now() > deadline) resolve(false);
      else setTimeout(probe, 400);
    };
    probe();
  });
}

const SPLASH = `data:text/html,${encodeURIComponent(`
<!doctype html><html><head><meta charset="utf-8"><style>
  html,body{height:100%;margin:0;background:#0e0f13;color:#c7c9d1;
    font-family:system-ui,-apple-system,Segoe UI,sans-serif;display:flex;
    align-items:center;justify-content:center;flex-direction:column;gap:1rem}
  .logo{color:#818cf8;font-weight:600;font-size:1.1rem;letter-spacing:.02em}
  .sub{color:#6b7280;font-size:.85rem}
  .spinner{width:26px;height:26px;border:3px solid #23262e;border-top-color:#6366f1;
    border-radius:50%;animation:spin 1s linear infinite}
  @keyframes spin{to{transform:rotate(360deg)}}
</style></head><body>
  <div class="spinner"></div>
  <div class="logo">Omics Desktop</div>
  <div class="sub">Starting analysis backend…</div>
</body></html>`)}`;

async function createWindow(): Promise<void> {
  const win = new BrowserWindow({
    width: 1320,
    height: 880,
    minWidth: 960,
    minHeight: 640,
    title: "Omics Desktop",
    backgroundColor: "#0e0f13",
    webPreferences: {
      preload: path.join(__dirname, "preload.js"),
      nodeIntegration: false,
      contextIsolation: true,
      sandbox: true,
    },
  });

  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: "deny" };
  });

  await win.loadURL(SPLASH);

  const ready = await waitForBackend();
  if (!ready) {
    await win.loadURL(
      `data:text/html,${encodeURIComponent(
        '<body style="background:#0e0f13;color:#ef4444;font-family:system-ui;padding:2rem">' +
          "Backend failed to start within 30s. Check that Python + the omics-backend " +
          "dependencies are installed (set OMICS_PYTHON to the right interpreter).</body>",
      )}`,
    );
    return;
  }

  if (VITE_DEV_SERVER_URL) {
    await win.loadURL(VITE_DEV_SERVER_URL);
    win.webContents.openDevTools({ mode: "detach" });
  } else {
    await win.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

app.whenReady().then(() => {
  startBackend();
  void createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) void createWindow();
  });
});

app.on("window-all-closed", () => {
  stopBackend();
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", stopBackend);
process.on("exit", stopBackend);
