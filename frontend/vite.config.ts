import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  base: "/static/workspace_v2/",
  plugins: [react(), tailwindcss(), {
    name: "no-page-entry-imports",
    generateBundle(_options, bundle) {
      const entries = new Set(Object.values(bundle)
        .filter(chunk => chunk.type === "chunk" && chunk.isEntry)
        .map(chunk => chunk.fileName));
      for (const chunk of Object.values(bundle)) {
        if (chunk.type !== "chunk") continue;
        for (const dependency of [...chunk.imports, ...chunk.dynamicImports]) {
          if (entries.has(dependency)) {
            this.error(`${chunk.fileName} imports page entry ${dependency}; this can remount a page loaded with a cache query.`);
          }
        }
      }
    },
  }],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  build: {
    outDir: path.resolve(__dirname, "../app/static/workspace_v2"),
    emptyOutDir: true,
    cssCodeSplit: false,
    rollupOptions: {
      // Keep side-effectful page bootstraps out of shared/lazy chunk exports.
      preserveEntrySignatures: "strict",
      input: {
        dashboard: path.resolve(__dirname, "./src/dashboard/main.tsx"),
        "shell-sidebar": path.resolve(__dirname, "./src/shell-sidebar/main.tsx"),
        "scenario-workspace": path.resolve(__dirname, "./src/scenario-workspace/main.tsx"),
        "employees-list": path.resolve(__dirname, "./src/employees-list/main.tsx"),
        "employee-detail": path.resolve(__dirname, "./src/employee-detail/main.tsx"),
        settings: path.resolve(__dirname, "./src/settings/main.tsx"),
        "bot-menu": path.resolve(__dirname, "./src/bot-menu/main.tsx"),
        documents: path.resolve(__dirname, "./src/documents/main.tsx"),
        grades: path.resolve(__dirname, "./src/grades/main.tsx"),
        messages: path.resolve(__dirname, "./src/messages/main.tsx"),
        "design-system": path.resolve(__dirname, "./src/design-system/main.tsx"),
        login: path.resolve(__dirname, "./src/login/main.tsx"),
      },
      output: {
        entryFileNames: "[name].js",
        assetFileNames: (assetInfo) => {
          if ((assetInfo.name || "").endsWith(".css")) {
            return "app.css";
          }
          return "assets/[name]-[hash][extname]";
        },
      },
    },
  },
});
