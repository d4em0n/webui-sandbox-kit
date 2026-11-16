import adapter from "@sveltejs/adapter-static";
import { vitePreprocess } from "@sveltejs/vite-plugin-svelte";
import path from "node:path";

export default {
  preprocess: vitePreprocess(),
  kit: {
    adapter: adapter({ pages: "dist", assets: "dist", fallback: "index.html" }),
    paths: { base: "/document-preview" },
    files: { lib: path.resolve(process.env.WEBUI_SOURCE, "src/lib") },
    alias: { $webui: path.resolve(process.env.WEBUI_SOURCE, "src") },
  },
};
