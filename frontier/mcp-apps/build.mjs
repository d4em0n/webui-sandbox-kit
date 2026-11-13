import { build } from 'esbuild';
import fs from 'node:fs/promises';

const result = await build({entryPoints: ['app.js'], bundle: true, minify: true, write: false, format: 'iife', target: ['safari15', 'chrome100']});
const css = await fs.readFile('dist/style.css', 'utf8');
const code = result.outputFiles[0].text.replace(/<\/script/gi, '<\\/script');
await fs.writeFile('dist/frontier.html', `<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><style>${css}
#host-notice:empty{display:none}#host-notice{padding:12px;border:1px solid #888;border-radius:12px;margin:10px}#host-notice textarea{display:block;width:100%;min-height:70px}body{overflow:auto}</style><link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.css"></head><body><div id="host-notice" role="status"></div><div id="app"></div><script type="application/json" id="spec">{}</script><script>${code}</script></body></html>`);
