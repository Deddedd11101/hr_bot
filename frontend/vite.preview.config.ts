import path from "node:path";
import { defineConfig } from "vite";
import base from "./vite.config";

export default defineConfig({
    ...base,
    build: {
        ...base.build,
        outDir: path.resolve(__dirname, "../../../outputs/adaptation-ui-preview/build"),
        rollupOptions: { input: path.resolve(__dirname, "adaptation-preview.html") },
    },
});
