const {chromium}=require('../.superpowers/review-browser-check/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try{
  const page=await browser.newPage(),base='http://127.0.0.1:8765',errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  const data=await(await page.request.get(base+'/api/analysis')).json();
  const before=await(await page.request.get(base+'/api/export')).json();
  const taxonomy=data.group_causes.M02;
  assert.equal(Object.keys(taxonomy.samples).length,20);
  await page.goto(base);await page.getByRole('button',{name:'Tổng quan',exact:true}).click();
  await page.locator('[data-summary-group="M02"] button').click();
  for(const [cause,name]of Object.entries(taxonomy.names)){
   const expected=Object.entries(taxonomy.samples).filter(([,v])=>v===cause).map(([sid])=>sid).sort();
   const card=page.locator(`[data-cause="${cause}"]`);await card.waitFor();
   assert.equal(await card.locator('b').innerText(),String(expected.length));assert.ok((await card.innerText()).includes(name));
   await card.click();assert.deepEqual((await page.locator('[data-analysis-sample]').evaluateAll(ns=>ns.map(n=>n.dataset.analysisSample))).sort(),expected);
   await page.getByRole('button',{name:'Quay lại nhóm nguyên nhân',exact:true}).click();
  }
  assert.equal(await page.locator('[data-cause]').count(),10);
  await page.locator('[data-cause="all"]').click();await page.locator('[data-analysis-sample="train_0025"]').click();
  const evidence=await page.getByLabel('Bằng chứng điều tra',{exact:true}).inputValue();
  assert.ok(evidence.includes('[M02 · Điều tra'));assert.ok(evidence.includes('[D02 · Điều tra'));
  await page.locator('[data-analysis-group="D02"]').click();await page.locator('[data-cause="scope"]').waitFor();
  assert.equal(await page.locator('[data-cause="scope"] b').innerText(),'50');
  await page.locator('[data-analysis-group="P01"]').click();await page.locator('[data-cause="pipeline"]').waitFor();
  assert.equal(await page.locator('[data-cause="pipeline"] b').innerText(),'21');
  assert.deepEqual(await(await page.request.get(base+'/api/export')).json(),before);assert.deepEqual(errors,[]);
  const result={passed:true,M02_samples:20,cause_groups:9,D02_scope:50,P01_pipeline:21,read_only:true};
  fs.writeFileSync('review_data/m02_investigation_20261103/browser_verification.json',JSON.stringify(result,null,2));console.log(result);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
