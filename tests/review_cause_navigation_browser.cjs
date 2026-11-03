// Read-only navigation check against the local review UI.
const {chromium}=require('../.superpowers/review-browser-check/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try {
  const page=await browser.newPage(),base='http://127.0.0.1:8765';
  const before=await(await page.request.get(base+'/api/export')).json();
  const analysis=await(await page.request.get(base+'/api/analysis')).json();
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base);
  await page.getByRole('button',{name:'Tổng quan',exact:true}).click();
  await page.locator('[data-summary-group="P01"] button').click();
  await page.locator('[data-cause="pipeline"]').waitFor();
  assert.equal(await page.locator('[data-analysis-sample]').count(),0);
  const related=analysis.records.filter(r=>r.primary_group==='P01'||r.secondary_groups.includes('P01'));
  const expected=related.filter(r=>analysis.investigations[r.sample_id]?.conclusion==='pipeline').map(r=>r.sample_id).sort();
  await page.locator('[data-cause="pipeline"]').click();
  assert.deepEqual((await page.locator('[data-analysis-sample]').evaluateAll(ns=>ns.map(n=>n.dataset.analysisSample))).sort(),expected);
  await page.getByRole('button',{name:'Quay lại nhóm nguyên nhân',exact:true}).click();
  await page.locator('[data-cause="insufficient"]').click();
  assert.equal(await page.locator('[data-analysis-sample]').count(),1);
  assert.equal(await page.locator('[data-analysis-sample]').getAttribute('data-analysis-sample'),'train_1178');
  await page.getByRole('button',{name:'Quay lại nhóm nguyên nhân',exact:true}).click();
  await page.locator('[data-cause="all"]').click();
  assert.equal(await page.locator('[data-analysis-sample]').count(),related.length);
  const group=Object.keys(analysis.groups).find(g=>analysis.records.some(r=>(r.primary_group===g||r.secondary_groups.includes(g))&&!analysis.investigations[r.sample_id]));
  await page.locator(`[data-analysis-group="${group}"]`).click();
  await page.locator('[data-cause="uninvestigated"]').click();
  assert.ok(await page.locator('[data-analysis-sample]').count()>0);
  assert.deepEqual(await(await page.request.get(base+'/api/export')).json(),before);
  assert.deepEqual(errors,[]);
  console.log('PASS: overview → causes → exact samples; back/all/uninvestigated; no data changes.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
