// QA-only browser check against a disposable instance with the mock provider.
const {chromium} = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const fs = require('fs');
const path = require('path');
(async () => {
  const base = process.env.KIT_QA_URL;
  const out = process.env.KIT_QA_STATE;
  if (!base || !out) throw Error('Set KIT_QA_URL and KIT_QA_STATE for an explicitly disposable stack');
  const credentials = JSON.parse(fs.readFileSync(path.join(out, 'credentials.json')));
  const browser = await chromium.launch({headless: true});
  const context = await browser.newContext({viewport: {width: 1280, height: 1000}, storageState: {cookies: [], origins: [{origin: base, localStorage: [{name: 'token', value: credentials.one.token}]}]}});
  const page = await context.newPage();
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base, {waitUntil: 'domcontentloaded'});
    await page.locator('#chat-input').waitFor({timeout: 60000});
    const okay = page.getByRole('button', {name: "Okay, Let's Go!"});
    if (await okay.isVisible()) await okay.click();
    await page.locator('#chat-input').fill('Show the Kyoto budget as an interactive Frontier widget.');
    await page.locator('#chat-input').press('Enter');
    let frame;
    const deadline = Date.now() + 120000;
    while (Date.now() < deadline) {
      for (const candidate of page.frames()) {
        if (candidate !== page.mainFrame() && await candidate.locator('html[data-frontier-ready=true]').count()) {frame = candidate; break;}
      }
      if (frame) break;
      await page.waitForTimeout(500);
    }
    if (!frame) throw Error('MCP widget absent: ' + (await page.locator('body').innerText()).slice(-1500));
    const output = await frame.locator('.cout').innerText();
    if (!/14[,.]?000/.test(output)) throw Error('Unexpected calculator output: ' + output);
    const input = frame.locator('input').first();
    await input.evaluate(element => {element.value = '3'; element.dispatchEvent(new Event('input', {bubbles: true}));});
    if (!/21[,.]?000/.test(await frame.locator('.cout').innerText())) throw Error('Calculator did not react to changed input');
    await page.screenshot({path: path.join(out, 'widget.png'), fullPage: true});
    fs.writeFileSync(path.join(out, 'browser-tests.json'), JSON.stringify([{name: 'Normal-user chat renders a native MCP App and interactive calculator', status: 'passed'}], null, 2));
    console.log('Native MCP App calculator browser check passed');
  } catch (error) {
    await page.screenshot({path: path.join(out, 'widget-failure.png'), fullPage: true});
    fs.writeFileSync(path.join(out, 'browser-tests.json'), JSON.stringify([{name: 'Normal-user chat renders a native MCP App and interactive calculator', status: 'failed', message: String(error)}], null, 2));
    throw error;
  } finally {
    fs.writeFileSync(path.join(out, 'browser-errors.json'), JSON.stringify(errors, null, 2));
    await browser.close();
  }
})().catch(error => {console.error(error); process.exit(1);});
