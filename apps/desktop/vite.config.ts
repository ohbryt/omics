import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Vite config for the renderer (React).
// The Electron main/preload are compiled separately via tsconfig.electron.json.
// See README.md for the full dev-flow.
export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    strictPort: true,
  },
  build: {
    outDir: "dist",
    emptyOutDir: true,
  },
});
