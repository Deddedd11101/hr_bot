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
    cssCodeSplit: false,
    rollupOptions: {
      input: {
        "scenario-workspace": path.resolve(__dirname, "./src/scenario-workspace/main.tsx"),
        "employees-list": path.resolve(__dirname, "./src/employees-list/main.tsx"),
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
