const {chromium}=require('../.superpowers/review-browser-check/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try {
  const page=await browser.newPage(),base='http://127.0.0.1:8765';
  const analysis=await(await page.request.get(base+'/api/analysis')).json();
  const before=JSON.parse(fs.readFileSync('logs/d02-ui-before-export.json','utf8'));
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);
  await page.getByRole('button',{name:'Tổng quan',exact:true}).click();
  await page.locator('[data-summary-group="D02"] button').click();
  const taxonomy=analysis.group_causes.D02;
  assert.equal(Object.keys(taxonomy.samples).length,68);
  for(const [cause,name] of Object.entries(taxonomy.names)) {
   const expected=Object.entries(taxonomy.samples).filter(([,v])=>v===cause).map(([sid])=>sid).sort();
   const card=page.locator(`[data-cause="${cause}"]`);
   await card.waitFor();assert.equal(await card.locator('b').innerText(),String(expected.length));
   assert.ok((await card.innerText()).includes(name));await card.click();
   assert.deepEqual((await page.locator('[data-analysis-sample]').evaluateAll(ns=>ns.map(n=>n.dataset.analysisSample))).sort(),expected);
   await page.getByRole('button',{name:'Quay lại nhóm nguyên nhân',exact:true}).click();
  }
  assert.equal(await page.locator('[data-cause]').count(),9);
  await page.locator('[data-analysis-group="P01"]').click();
  await page.locator('[data-cause="pipeline"]').waitFor();
  assert.equal(await page.locator('[data-cause="pipeline"] b').innerText(),'21');
  assert.deepEqual(await(await page.request.get(base+'/api/export')).json(),before);
  assert.deepEqual(errors,[]);
  console.log('PASS: D02 eight cause counts and exact sample sets; P01 pipeline=21; stored reviews/feedback/investigations unchanged.');
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
