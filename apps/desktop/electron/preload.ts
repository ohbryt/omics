/**
 * Electron preload script — executed in a privileged context before the renderer
 * loads, but with contextIsolation: true so the renderer cannot access Node APIs.
 *
 * SECURITY CONTRACT (SPEC §2, §10.1):
 *   - Only a thin, explicitly enumerated API is exposed via contextBridge.
 *   - No vendor secrets (API keys, tokens) are ever passed through this bridge.
 *   - The renderer communicates with the FastAPI backend (http://127.0.0.1:8765)
 *     exclusively via the typed fetch-based client in src/api/client.ts.
 *   - ipcRenderer is NOT exposed. All backend communication is plain HTTP.
 */

import { contextBridge } from "electron";

/**
 * OmicsShellAPI is the only surface area exposed to the renderer.
 * Keep it minimal — prefer HTTP calls to the backend over IPC.
 */
export interface OmicsShellAPI {
  /** The platform string, useful for rendering OS-specific hints. */
  platform: string;
  /**
   * The base URL of the FastAPI backend. Hardcoded to localhost; the renderer
   * uses this when constructing fetch calls so the URL is not duplicated.
   */
  backendBaseUrl: string;
}

contextBridge.exposeInMainWorld("omicsShell", {
  platform: process.platform,
  // Backend always runs locally. Port matches SPEC §10 and the FastAPI app.
  backendBaseUrl: "http://127.0.0.1:8765",
} satisfies OmicsShellAPI);
