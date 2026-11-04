const { chromium } = require('../.superpowers/review-browser-check/node_modules/playwright');
const assert = require('node:assert/strict');
(async () => {
  const browser = await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
  try {
    const page = await browser.newPage();
    const errors = [], writes = [];
    page.on('pageerror', e => errors.push(e.message));
    page.on('request', r => {if (!['GET','HEAD'].includes(r.method())) writes.push(r.url());});
    const base = 'http://127.0.0.1:8765';
    const before = await (await page.request.get(base+'/api/reviews')).json();
    const data = await (await page.request.get(base+'/api/analysis')).json();
    assert.equal(data.priority_review_ids.length, 13);
    await page.goto(base);
    await page.getByRole('button',{name:'Phân tích lỗi',exact:true}).click();
    const filter = page.getByRole('checkbox',{name:'Cần đối chiếu comment cũ (13)',exact:true});
    await filter.check();
    assert.deepEqual((await page.locator('[data-analysis-sample]').evaluateAll(nodes => nodes.map(n=>n.dataset.analysisSample))).sort(), [...data.priority_review_ids].sort());
    await page.locator('[data-analysis-sample="train_1178"]').click();
    assert((await page.locator('.analysis-detail').innerText()).includes('available=true'));
    await page.getByRole('textbox',{name:'Tìm nhóm hoặc sample',exact:true}).fill('train_1412');
    assert.equal(await page.locator('[data-analysis-sample]').count(),1);
    await filter.uncheck();
    assert.equal(await page.locator('[data-analysis-sample]').count(),300);
    assert.deepEqual(await (await page.request.get(base+'/api/reviews')).json(), before);
    assert.deepEqual(errors,[]); assert.deepEqual(writes,[]);
    console.log('PASS: exact 13 IDs, detail, search, reset to 300, no writes, reviews unchanged.');
  } finally { await browser.close(); }
})().catch(e => {console.error(e);process.exitCode=1;});
