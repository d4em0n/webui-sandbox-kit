// Real SDK host: preview navigation must not fetch documents or replace downloads.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import http from 'node:http';
import {createRequire} from 'node:module';
import {build} from 'esbuild';

const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const report = process.env.FRONTIER_FILES_REPORT;
if (!report) throw new Error('Set FRONTIER_FILES_REPORT to a writable JSON report path');
const html = await fs.readFile(new URL('../dist/frontier.html', import.meta.url), 'utf8');
const download = 'https://webui.example/api/v1/files/synthetic-id/content';
const preview = 'https://webui.example/document-preview/?file_id=synthetic-id';
const spec = {blocks: [{type: 'file', format: 'docx', name: 'Synthetic.docx', url: download, preview_url: preview,
  preview: 'data:image/gif;base64,R0lGODlhAQABAIAAAAAAAP///ywAAAAAAQABAAACAUwAOw=='}], _ui: {actions: false}};
const bundle = await build({stdin: {resolveDir: process.cwd(), contents: `
import {AppBridge, PostMessageTransport} from '@modelcontextprotocol/ext-apps/app-bridge';
const frame = document.querySelector('iframe');
const bridge = new AppBridge(null, {name: 'Synthetic file card QA', version: '1'}, {openLinks: {}, serverTools: {}},
  {hostContext: {theme: 'light', displayMode: 'inline', containerDimensions: {width: 390}}});
window.links = [];
window.calls = [];
bridge.oncalltool = async params => {
  window.calls.push({name: params.name, arguments: params.arguments});
  if (params.name === 'craft_file') return {content: [], structuredContent: {path: '/home/user/Inbox/Synthetic.docx'}};
  if (params.name === 'craft_display') return {content: [], structuredContent: {spec: ${JSON.stringify(spec)}}};
  throw new Error('Unexpected tool: ' + params.name);
};
bridge.onopenlink = async ({url}) => { window.links.push(url); return {}; };
bridge.onsizechange = ({height}) => { frame.style.height = height + 'px'; };
window.sendSpec = spec => bridge.sendToolResult({structuredContent: {spec}, content: []});
bridge.oninitialized = () => window.sendSpec(${JSON.stringify(spec)});
await bridge.connect(new PostMessageTransport(frame.contentWindow, frame.contentWindow));
frame.srcdoc = ${JSON.stringify(html)};
`}, bundle: true, format: 'esm', write: false});
const server = http.createServer((req, res) => {
  res.setHeader('content-type', req.url === '/bridge.js' ? 'text/javascript' : 'text/html');
  res.end(req.url === '/bridge.js' ? bundle.outputFiles[0].text : '<!doctype html><iframe style="width:390px;height:300px;border:0" sandbox="allow-scripts"></iframe><script type="module" src="/bridge.js"></script>');
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const records = [];
let browser;
try {
  browser = await chromium.launch({headless: true});
  const page = await browser.newPage({viewport: {width: 430, height: 850}});
  const errors = [], fileRequests = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', request => { if (request.url().startsWith('https://webui.example/')) fileRequests.push(request.url()); });
  await page.route('https://cdn.jsdelivr.net/**', route => route.fulfill({body: '', contentType: 'text/css'}));
  await page.goto('http://127.0.0.1:' + server.address().port);
  const frame = page.frameLocator('iframe');
  await frame.getByRole('button', {name: 'Open preview', exact: true}).waitFor();
  assert.equal(await frame.locator('img.fprev').count(), 1);
  assert.equal(await frame.getByRole('button', {name: 'Download', exact: true}).count(), 1);
  assert.deepEqual(fileRequests, []);
  records.push({name: 'file card retains thumbnail and download without fetching document bytes', status: 'passed'});
  await frame.getByRole('button', {name: 'Open preview', exact: true}).click();
  await page.waitForFunction(url => window.links.includes(url), preview);
  await frame.getByRole('button', {name: 'Download', exact: true}).click();
  await page.waitForFunction(url => window.links.includes(url), download);
  assert.deepEqual(await page.evaluate(() => window.links), [preview, download]);
  records.push({name: 'preview and download use the normal MCP host open-link handler with distinct URLs', status: 'passed'});
  delete spec.blocks[0].preview_url;
  await page.evaluate(value => window.sendSpec(value), spec);
  await frame.getByRole('button', {name: 'Open preview', exact: true}).waitFor({state: 'detached'});
  assert.equal(await frame.getByRole('button', {name: 'Download', exact: true}).count(), 1);
  assert.deepEqual(errors, []);
  records.push({name: 'cards without preview metadata keep existing behavior; no JavaScript exceptions', status: 'passed'});
  await page.evaluate(value => window.sendSpec(value), {title: 'Synthetic export', blocks: [{type: 'text', md: 'Synthetic document'}], _ui: {card: 'synthetic-card'}});
  await frame.getByRole('button', {name: 'Export', exact: true}).click();
  // Test the RPC sequence independently of the upstream floating menu's positioning.
  await frame.getByRole('button', {name: /Word document/}).evaluate(button => button.click());
  await frame.getByRole('button', {name: 'Open preview', exact: true}).waitFor();
  assert.deepEqual(await page.evaluate(() => window.calls), [
    {name: 'craft_file', arguments: {card: 'synthetic-card', format: 'docx', open_in_desktop: false}},
    {name: 'craft_display', arguments: {path: '/home/user/Inbox/Synthetic.docx'}},
  ]);
  assert.deepEqual(errors, []);
  records.push({name: 'widget Export generates then explicitly displays the returned path', status: 'passed'});
} catch (error) {
  records.push({name: 'file card preview', status: 'failed', message: String(error)});
  throw error;
} finally {
  await fs.writeFile(report, JSON.stringify(records, null, 2) + '\n');
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
