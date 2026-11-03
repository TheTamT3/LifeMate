// All writes go to a disposable data directory on port 8769.
const {chromium}=require('../.superpowers/review-browser-check/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try {
  const page=await browser.newPage(), base='http://127.0.0.1:8769';
  const errors=[]; page.on('pageerror',e=>errors.push(e.message));
  const before=await(await page.request.get(base+'/api/export')).json();
  await page.goto(base);
  await page.getByRole('button',{name:'Phân tích lỗi',exact:true}).click();
  const evidence=page.getByRole('textbox',{name:'Bằng chứng điều tra',exact:true});
  await page.getByRole('combobox',{name:'Kết luận nguyên nhân',exact:true}).selectOption('pipeline');
  await evidence.fill('Tool write succeeded; no next model turn.');
  const first=await page.locator('[data-analysis-sample][aria-pressed="true"]').getAttribute('data-analysis-sample');
  await page.locator('[data-analysis-sample]').filter({hasNot:page.locator('[aria-pressed="true"]')}).nth(1).click();
  await page.locator(`[data-analysis-sample="${first}"]`).click();
  assert.equal(await evidence.inputValue(),'Tool write succeeded; no next model turn.');
  await page.getByRole('button',{name:'Nhận xét',exact:true}).click();
  await page.getByRole('button',{name:'Phân tích lỗi',exact:true}).click();
  assert.equal(await evidence.inputValue(),'Tool write succeeded; no next model turn.');
  await page.getByRole('button',{name:'Lưu điều tra',exact:true}).click();
  await page.getByText('Đã lưu điều tra vào SQLite.',{exact:true}).waitFor();
  await page.reload();
  await page.getByRole('button',{name:'Phân tích lỗi',exact:true}).click();
  assert.equal(await evidence.inputValue(),'Tool write succeeded; no next model turn.');
  const data=await(await page.request.get(base+'/api/analysis')).json();
  const value={analysis_key:data.feedback_key,conclusion:'pipeline',replay:'confirmed',revision:0};
  assert.equal((await page.request.put(base+'/api/investigation/'+first,{data:value})).status(),409);
  assert.equal((await page.request.put(base+'/api/investigation/'+first,{data:{...value,analysis_key:'stale'}})).status(),409);
  assert.equal((await page.request.put(base+'/api/investigation/unknown',{data:value})).status(),404);
  assert.equal((await page.request.put(base+'/api/investigation/'+first,{data:{...value,conclusion:'bad'}})).status(),400);
  const after=await(await page.request.get(base+'/api/export')).json();
  assert.deepEqual(after.reviews,before.reviews);
  assert.deepEqual(after.analysis_feedback,before.analysis_feedback);
  assert.equal(after.investigations.length,1);
  assert.deepEqual(errors,[]);
  console.log('PASS: investigation persistence, draft navigation, validation, conflicts, export and existing data isolation.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
