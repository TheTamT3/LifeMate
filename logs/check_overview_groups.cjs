const {chromium}=require('../.superpowers/review-browser-check/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try {
  const page=await browser.newPage(); const base='http://127.0.0.1:8765';
  const errors=[],writes=[];
  page.on('pageerror',e=>errors.push(e.message));
  page.on('request',r=>{if(!['GET','HEAD'].includes(r.method()))writes.push(r.url());});
  const before=await(await page.request.get(base+'/api/reviews')).json();
  const data=await(await page.request.get(base+'/api/analysis')).json();
  const counts={}; for(const r of data.records)counts[r.primary_group]=(counts[r.primary_group]||0)+1;
  const expected=Object.keys(data.groups).filter(id=>/^[MPD]/.test(id)&&counts[id]).sort((a,b)=>counts[b]-counts[a]||a.localeCompare(b));
  await page.goto(base);
  await page.getByRole('button',{name:'Tổng quan',exact:true}).click();
  await page.locator('[data-summary-group]').first().waitFor();
  assert.deepEqual(await page.locator('[data-summary-group]').evaluateAll(rows=>rows.map(r=>r.dataset.summaryGroup)),expected);
  for(const id of expected)assert.equal(await page.locator(`[data-summary-group="${id}"] td`).last().innerText(),String(counts[id]));
  await page.locator('[data-summary-group="P01"] button').click();
  await page.getByRole('heading',{name:'Agent lệch ở bước nào?'}).waitFor();
  assert.equal(await page.locator('[data-analysis-group="P01"]').getAttribute('aria-pressed'),'true');
  assert.equal(await page.locator('[data-analysis-sample]').count(),data.records.filter(r=>r.primary_group==='P01'||r.secondary_groups.includes('P01')).length);
  assert.deepEqual(await(await page.request.get(base+'/api/reviews')).json(),before);
  assert.deepEqual(writes,[]);assert.deepEqual(errors,[]);
  console.log(JSON.stringify({groups:expected.length,samples:expected.reduce((s,id)=>s+counts[id],0),sorted:true,navigation:true,reviews_unchanged:true}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
