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
  const expectedCounts={M03:20,M14:10,M05:11,M19:8,M06:18,M18:8,D03:28};
  const samples=new Set(),groups={};
  await page.goto(base);
  for(const [group,count]of Object.entries(expectedCounts)){
   const taxonomy=data.group_causes[group];
   assert.equal(Object.keys(taxonomy.samples).length,count);
   await page.getByRole('button',{name:'Tổng quan',exact:true}).click();
   await page.locator(`[data-summary-group="${group}"] button`).click();
   for(const [cause,name]of Object.entries(taxonomy.names)){
    const expected=Object.entries(taxonomy.samples).filter(([,v])=>v===cause).map(([sid])=>sid).sort();
    expected.forEach(s=>samples.add(s));
    const card=page.locator(`[data-cause="${cause}"]`);await card.waitFor();
    assert.equal(await card.locator('b').innerText(),String(expected.length));
    assert.ok((await card.innerText()).includes(name));
    await card.click();
    assert.deepEqual((await page.locator('[data-analysis-sample]').evaluateAll(ns=>ns.map(n=>n.dataset.analysisSample))).sort(),expected);
    await page.getByRole('button',{name:'Quay lại nhóm nguyên nhân',exact:true}).click();
   }
   assert.equal(await page.locator('[data-cause]').count(),Object.keys(taxonomy.names).length+1);
   await page.locator('[data-cause="all"]').click();
   const first=Object.keys(taxonomy.samples)[0];
   await page.locator(`[data-analysis-sample="${first}"]`).click();
   const evidence=await page.getByLabel('Bằng chứng điều tra',{exact:true}).inputValue();
   assert.ok(evidence.includes(`[${group} · Điều tra`));
   groups[group]={samples:count,cause_groups:Object.keys(taxonomy.names).length};
  }
  assert.equal(samples.size,84);
  await page.locator('[data-analysis-group="M03"]').click();
  await page.locator('[data-cause="wrong_workflow"]').click();
  await page.locator('[data-analysis-sample="train_0247"]').click();
  const overlap=await page.getByLabel('Bằng chứng điều tra',{exact:true}).inputValue();
  for(const group of ['M04','M03','M06'])assert.ok(overlap.includes(`[${group} · Điều tra`));
  await page.locator('[data-analysis-group="D02"]').click();await page.locator('[data-cause="scope"]').waitFor();
  assert.equal(await page.locator('[data-cause="scope"] b').innerText(),'50');
  await page.locator('[data-analysis-group="P01"]').click();await page.locator('[data-cause="pipeline"]').waitFor();
  assert.equal(await page.locator('[data-cause="pipeline"] b').innerText(),'21');
  assert.deepEqual(await(await page.request.get(base+'/api/export')).json(),before);
  assert.deepEqual(errors,[]);
  const result={passed:true,groups,unique_samples:samples.size,D02_scope:50,P01_pipeline:21,read_only:true,console_errors:errors};
  fs.writeFileSync('review_data/priority_six_investigation_20261103/browser_verification.json',JSON.stringify(result,null,2));console.log(result);
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
