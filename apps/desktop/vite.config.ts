import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import electron from "vite-plugin-electron/simple";

// Renderer (React) + Electron main/preload, wired by vite-plugin-electron.
// `npm run dev` launches the actual Electron desktop window (the plugin sets
// VITE_DEV_SERVER_URL and starts Electron); `npm run build` produces dist/ +
// dist-electron/ for packaging.
export default defineConfig({
  plugins: [
    react(),
    electron({
      main: { entry: "electron/main.ts" },
      preload: { input: "electron/preload.ts" },
      // Renderer uses only fetch + DOM, no Node APIs — no renderer plugin needed.
    }),
  ],
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
