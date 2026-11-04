const {chromium}=require('../.superpowers/review-browser-check/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try {
  const page=await browser.newPage(); const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('http://127.0.0.1:8765/');
  await page.getByRole('button',{name:'Phân tích lỗi',exact:true}).click();
  for (const [sid,conclusion] of [['train_0672','pipeline'],['train_1178','insufficient']]) {
   await page.locator(`[data-analysis-sample="${sid}"]`).click();
   assert.equal(await page.getByRole('combobox',{name:'Kết luận nguyên nhân',exact:true}).inputValue(),conclusion);
   assert.equal(await page.getByRole('combobox',{name:'Trạng thái replay',exact:true}).inputValue(),'not_run');
   assert.ok((await page.getByRole('textbox',{name:'Bằng chứng điều tra',exact:true}).inputValue()).includes('Chưa replay') || (await page.getByRole('textbox',{name:'Bằng chứng điều tra',exact:true}).inputValue()).includes('chưa replay'));
  }
  assert.deepEqual(errors,[]);
  console.log('PASS: saved investigations visible in live UI, replay not run; read-only browser check.');
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
