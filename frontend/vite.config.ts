import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../app/static/workspace_v2"),
    emptyOutDir: true,
    rollupOptions: {
      input: path.resolve(__dirname, "./src/scenario-workspace/main.tsx"),
      output: {
        entryFileNames: "scenario-workspace.js",
        assetFileNames: (assetInfo) => {
          if ((assetInfo.name || "").endsWith(".css")) {
            return "scenario-workspace.css";
          }
          return "assets/[name]-[hash][extname]";
        },
      },
    },
  },
});
