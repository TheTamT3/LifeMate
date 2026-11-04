const { chromium } = require('../.superpowers/review-browser-check/node_modules/playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({ executablePath: 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1700, height: 1050 } });
    const errors = [], writes = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => { if (r.method() !== 'GET') writes.push(r.url()); });
    await page.goto('http://127.0.0.1:8767/');
    await page.locator('#detail h2').filter({ hasText: 'train_0672' }).waitFor();
    assert.equal(await page.locator('[data-group]').count(), 17);
    await page.locator('[data-group="M10"]').click();
    await page.locator('[data-sample="train_1697"]').click();
    await page.locator('#detail details').first().locator('summary').click();
    assert((await page.locator('#detail').innerText()).includes('lock_id'));
    await page.locator('#search').fill('train_0454');
    await page.locator('#detail h2').filter({ hasText: 'train_0454' }).waitFor();
    await page.locator('#search').fill('');
    await page.locator('#layer').selectOption('P');
    assert.equal(await page.locator('[data-group]').count(), 1);
    await page.locator('[data-sample="train_0672"]').click();
    await page.screenshot({ path: 'logs/error-analysis-mockup/preview.png', fullPage: true });
    assert.deepEqual(errors, []);
    assert.deepEqual(writes, []);
    console.log('PASS: groups, sample navigation, reasoning, search, layer filter; no browser errors or writes.');
  } finally { await browser.close(); }
})().catch(e => { console.error(e); process.exitCode = 1; });
