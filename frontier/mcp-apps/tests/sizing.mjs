// Synthetic SDK iframe regression: no account, provider, live server or KVM needed.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import http from 'node:http';
import {createRequire} from 'node:module';
import {build} from 'esbuild';

const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const report = process.env.FRONTIER_SIZING_REPORT;
if (!report) throw new Error('Set FRONTIER_SIZING_REPORT to a writable JSON report path');
const html = await fs.readFile(new URL('../dist/frontier.html', import.meta.url), 'utf8');
const spec = count => ({title: 'Synthetic sizing fixture', blocks: Array.from({length: count}, (_, i) => ({type: 'text', md: `Review paragraph ${i + 1}. Synthetic content for iframe layout.`}))});
const bundle = await build({stdin: {resolveDir: process.cwd(), contents: `
import {AppBridge, PostMessageTransport} from '@modelcontextprotocol/ext-apps/app-bridge';
const frame = document.querySelector('iframe');
const limit = new URL(location.href).searchParams.get('limit');
const dimensions = limit ? {width: 480, maxHeight: Number(limit)} : {width: 480};
const bridge = new AppBridge(null, {name: 'Synthetic kit QA', version: '1'}, {},
  {hostContext: {theme: 'light', displayMode: 'inline', containerDimensions: dimensions}});
window.heights = [];
bridge.onsizechange = ({height}) => { window.heights.push(height); frame.style.height = height + 'px'; };
window.sendSpec = spec => bridge.sendToolResult({structuredContent: {spec}, content: []});
bridge.oninitialized = () => window.sendSpec(${JSON.stringify(spec(90))});
await bridge.connect(new PostMessageTransport(frame.contentWindow, frame.contentWindow));
frame.srcdoc = ${JSON.stringify(html)};
`}, bundle: true, format: 'esm', write: false});
const server = http.createServer((req, res) => {
  res.setHeader('content-type', req.url === '/bridge.js' ? 'text/javascript' : 'text/html');
  res.end(req.url === '/bridge.js' ? bundle.outputFiles[0].text : '<!doctype html><iframe style="width:480px;height:300px;border:0" sandbox="allow-scripts"></iframe><script type="module" src="/bridge.js"></script>');
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const records = [];
let browser;
try {
  browser = await chromium.launch({headless: true});
  const page = await browser.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('https://cdn.jsdelivr.net/**', route => route.fulfill({body: '', contentType: 'text/css'}));
  const base = 'http://127.0.0.1:' + server.address().port;
  await page.goto(base);
  await page.waitForFunction(() => window.heights?.some(height => height > 1600));
  records.push({name: 'no host maximum preserves content taller than 1600px', status: 'passed'});
  await page.evaluate(value => window.sendSpec(value), spec(1));
  await page.waitForFunction(() => window.heights?.at(-1) > 0 && window.heights.at(-1) < 1000);
  records.push({name: 'large iframe shrinks after a shorter tool result', status: 'passed'});
  await page.goto(base + '/?limit=1200');
  await page.waitForFunction(() => window.heights?.includes(1200));
  assert.ok((await page.evaluate(() => window.heights)).every(height => height <= 1200));
  records.push({name: 'explicit host height maximum remains enforced', status: 'passed'});
  assert.deepEqual(errors, []);
  records.push({name: 'SDK host and widget have no JavaScript exceptions', status: 'passed'});
} catch (error) {
  records.push({name: 'synthetic SDK sizing', status: 'failed', message: String(error)});
  throw error;
} finally {
  await fs.writeFile(report, JSON.stringify(records, null, 2) + '\n');
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
