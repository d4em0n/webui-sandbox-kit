import { sveltekit } from "@sveltejs/kit/vite";
import { defineConfig } from "vite";
import path from "node:path";
export default defineConfig({
  plugins: [
    {
      name: "pdf-touch-scrolling",
      enforce: "pre",
      resolveId(id, importer) {
        if (id === "panzoom" && importer?.endsWith("/common/PDFViewer.svelte"))
          return path.resolve("src/pdf-panzoom.js");
      },
    },
    sveltekit(),
  ],
  resolve: {
    // The standard PDF.js worker needs TypedArray.toHex, absent in older WebViews.
    alias: [
      {
        find: "upstream-panzoom",
        replacement: path.resolve(
          process.env.WEBUI_SOURCE,
          "node_modules/panzoom/index.js",
        ),
      },
      {
        find: /^pdfjs-dist$/,
        replacement: path.resolve(
          process.env.WEBUI_SOURCE,
          "node_modules/pdfjs-dist/legacy/build/pdf.mjs",
        ),
      },
      {
        find: "pdfjs-dist/build",
        replacement: path.resolve(
          process.env.WEBUI_SOURCE,
          "node_modules/pdfjs-dist/legacy/build",
        ),
      },
    ],
  },
  define: {
    APP_VERSION: JSON.stringify("0.13.3"),
    APP_BUILD_HASH: JSON.stringify("b0e6098e940942281d9c83f3529ea117287a3a22"),
    APP_BUILD_CHANNEL: JSON.stringify("preview"),
  },
  build: { target: "es2022" },
  worker: { format: "es" },
});
