/**
 * Electron main process — desktop shell for the AI-assisted omics app.
 *
 * SECURITY CONTRACT (SPEC §2, §10.1):
 *   - Vendor API keys (OpenAI, Anthropic) NEVER live here or in the renderer.
 *   - All AI calls go through the FastAPI backend (http://127.0.0.1:8765).
 *   - The backend reads credentials from the OS keychain (dev) or backend-mediated
 *     OAuth/OIDC (prod). They are never returned to this process or the renderer.
 *   - Raw sequence data, full expression matrices, and patient metadata are never
 *     sent to vendor models unless ai.send_raw_data: true is set in config.yaml.
 */

import { app, BrowserWindow, shell } from "electron";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// Vite builds the renderer to dist/ when running `npm run build`.
// In dev mode vite-plugin-electron injects VITE_DEV_SERVER_URL.
const VITE_DEV_SERVER_URL = process.env["VITE_DEV_SERVER_URL"];

function createWindow(): void {
  const win = new BrowserWindow({
    width: 1280,
    height: 900,
    title: "Omics Desktop",
    webPreferences: {
      // Load the preload script so contextBridge can expose the safe API.
      preload: path.join(__dirname, "preload.js"),
      // Disable Node.js integration in the renderer — the renderer is an
      // untrusted web surface and must only talk to the backend via HTTP.
      nodeIntegration: false,
      contextIsolation: true,
      // Disable remote module access for defence in depth.
      sandbox: true,
    },
  });

  // Open external links in the OS browser, not in Electron.
  win.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: "deny" };
  });

  if (VITE_DEV_SERVER_URL) {
    void win.loadURL(VITE_DEV_SERVER_URL);
    win.webContents.openDevTools();
  } else {
    void win.loadFile(path.join(__dirname, "../dist/index.html"));
  }
}

app.whenReady().then(() => {
  createWindow();

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});
