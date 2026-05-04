import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

// publicDir points at the repo-root public/ so dev and build both serve
// the same changes.json / rss.xml that the nightly Action regenerates.
export default defineConfig({
  plugins: [react()],
  publicDir: path.resolve(__dirname, "..", "public"),
  server: { port: 5199, strictPort: true },
  preview: { port: 5199, strictPort: true },
});
