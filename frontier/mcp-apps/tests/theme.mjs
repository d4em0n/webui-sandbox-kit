// Real SDK host and renderer; synthetic data, no running installation or account.
import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
import http from 'node:http';
import {createRequire} from 'node:module';
import {build} from 'esbuild';

const require = createRequire(import.meta.url);
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const report = process.env.FRONTIER_THEME_REPORT;
if (!report) throw new Error('Set FRONTIER_THEME_REPORT to a writable JSON report path');
const html = await fs.readFile(new URL('../dist/frontier.html', import.meta.url), 'utf8');
const spec = {
  title: 'Kyoto theme regression', subtitle: 'Synthetic itinerary and export',
  blocks: [
    {type: 'text', md: 'Readable **itinerary** text and controls.'},
    {type: 'calculator', title: 'Budget', currency: '¥',
      inputs: [{id: 'days', label: 'Days', value: 2}, {id: 'daily', label: 'Daily budget', value: 5000}],
      outputs: [{label: 'Trip total', expr: 'days*daily', format: 'money'}]},
    {type: 'chart', title: 'Costs', kind: 'bar', labels: ['Meals', 'Transit'], series: [{name: 'Budget', data: [3000, 1000]}]},
    {type: 'file', name: 'Kyoto.docx', format: 'docx', size: 4096, url: 'https://example.com/Kyoto.docx'},
  ],
  followups: ['Plan another day'],
};
const bundle = await build({stdin: {resolveDir: process.cwd(), contents: `
import {AppBridge, PostMessageTransport} from '@modelcontextprotocol/ext-apps/app-bridge';
const frame = document.querySelector('iframe');
const theme = new URL(location.href).searchParams.get('theme') || 'light';
const bridge = new AppBridge(null, {name: 'Synthetic theme QA', version: '1'}, {},
  {hostContext: {theme, displayMode: 'inline', containerDimensions: {width: 760}}});
bridge.onsizechange = ({height}) => { frame.style.height = height + 'px'; };
function background(theme) { document.body.style.background = theme === 'dark' ? '#171717' : '#ffffff'; }
background(theme);
window.changeContext = context => { if (context.theme) background(context.theme); bridge.setHostContext(context); };
window.sendSpec = () => bridge.sendToolResult({structuredContent: {spec: ${JSON.stringify(spec)}}, content: []});
bridge.oninitialized = window.sendSpec;
await bridge.connect(new PostMessageTransport(frame.contentWindow, frame.contentWindow));
frame.srcdoc = ${JSON.stringify(html)};
`}, bundle: true, format: 'esm', write: false});
const server = http.createServer((req, res) => {
  res.setHeader('content-type', req.url === '/bridge.js' ? 'text/javascript' : 'text/html');
  res.end(req.url === '/bridge.js' ? bundle.outputFiles[0].text : '<!doctype html><iframe style="width:760px;height:300px;border:0" sandbox="allow-scripts"></iframe><script type="module" src="/bridge.js"></script>');
});
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
const records = [];
let browser;
function luminance(color) {
  const channels = color.match(/[\d.]+/g).slice(0, 3).map(Number).map(value => {
    const c = value / 255;
    return c <= .04045 ? c / 12.92 : ((c + .055) / 1.055) ** 2.4;
  });
  return channels[0] * .2126 + channels[1] * .7152 + channels[2] * .0722;
}
function contrast(a, b) {
  const [dark, light] = [luminance(a), luminance(b)].sort((a, b) => a - b);
  return (light + .05) / (dark + .05);
}
async function checkTheme(frame, expected) {
  const styles = await frame.evaluate(() => {
    const root = document.documentElement;
    const color = selector => {
      const element = document.querySelector(selector);
      const style = getComputedStyle(element);
      let background = element;
      while (background && getComputedStyle(background).backgroundColor === 'rgba(0, 0, 0, 0)') background = background.parentElement;
      return {fg: style.color, bg: background ? getComputedStyle(background).backgroundColor : null};
    };
    return {theme: root.dataset.theme, dark: root.classList.contains('dark'), light: root.classList.contains('light'),
      isDark: window.IUI.isDark(), scheme: root.style.colorScheme,
      controls: ['.panel', '.cin input[type=number]', '.cout .v', '.btn.pri'].map(color),
      surface: getComputedStyle(document.querySelector('.panel')).backgroundColor};
  });
  assert.equal(styles.theme, expected);
  assert.equal(styles.dark, expected === 'dark');
  assert.equal(styles.light, expected === 'light');
  assert.equal(styles.isDark, expected === 'dark');
  assert.equal(styles.scheme, expected);
  assert.equal(luminance(styles.surface) < .1, expected === 'dark');
  for (const control of styles.controls) assert.ok(contrast(control.fg, control.bg) >= 4.5, JSON.stringify(control));
}
try {
  browser = await chromium.launch({headless: true});
  const page = await browser.newPage({colorScheme: 'light'});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  await page.route('https://cdn.jsdelivr.net/**', route => route.fulfill({body: '', contentType: 'text/css'}));
  const base = 'http://127.0.0.1:' + server.address().port;
  async function open(theme) {
    await page.goto(base + '/?theme=' + theme);
    const frame = page.frames().find(frame => frame !== page.mainFrame());
    await frame.locator('html[data-frontier-ready=true]').waitFor();
    return frame;
  }
  let frame = await open('dark');
  if (process.env.FRONTIER_THEME_SCREENSHOT) await page.screenshot({path: process.env.FRONTIER_THEME_SCREENSHOT, fullPage: true});
  await checkTheme(frame, 'dark');
  records.push({name: 'Dark host context overrides light browser preference with readable panels and controls', status: 'passed'});
  const days = frame.locator('input[type=number]').first();
  await days.fill('3');
  assert.match(await frame.locator('.cout').innerText(), /15,?000/);
  await page.evaluate(() => window.changeContext({theme: 'light'}));
  await frame.waitForFunction(() => document.documentElement.dataset.theme === 'light');
  await checkTheme(frame, 'light');
  assert.equal(await days.inputValue(), '3');
  records.push({name: 'Dark-to-light host notification updates theme without losing calculator state', status: 'passed'});
  await page.evaluate(() => window.changeContext({theme: 'dark'}));
  await frame.waitForFunction(() => document.documentElement.dataset.theme === 'dark');
  await checkTheme(frame, 'dark');
  await page.evaluate(() => window.changeContext({containerDimensions: {width: 640}}));
  await checkTheme(frame, 'dark');
  assert.equal(await days.inputValue(), '3');
  records.push({name: 'Light-to-dark and unrelated context updates retain theme and interactive state', status: 'passed'});
  const previousTitle = await frame.locator('h1.t').elementHandle();
  await page.evaluate(() => window.sendSpec());
  await frame.waitForFunction(previous => !previous.isConnected, previousTitle);
  await checkTheme(frame, 'dark');
  assert.equal(await days.inputValue(), '3');
  records.push({name: 'Re-rendered cards retain the dark palette and saved calculator values', status: 'passed'});
  await page.emulateMedia({colorScheme: 'dark'});
  frame = await open('light');
  await checkTheme(frame, 'light');
  records.push({name: 'Light host context overrides dark browser preference', status: 'passed'});
  assert.deepEqual(errors, []);
  records.push({name: 'SDK theme scenarios produce no JavaScript exceptions', status: 'passed'});
} catch (error) {
  records.push({name: 'Frontier MCP theme regression', status: 'failed', message: String(error)});
  throw error;
} finally {
  await fs.writeFile(report, JSON.stringify(records, null, 2) + '\n');
  if (browser) await browser.close();
  await new Promise(resolve => server.close(resolve));
}
