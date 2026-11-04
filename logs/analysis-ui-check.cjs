const {chromium}=require('../.superpowers/review-browser-check/node_modules/playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1700,height:1050}});
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  const base='http://127.0.0.1:8768';
  const existing=await (await page.request.get(base+'/api/reviews')).json();
  const saved=await page.request.put(base+'/api/review/train_0672',{data:{status:'reviewed',verdict:'Agent đúng',tags:[],comment:'Current review differs from pilot',revision:existing.train_0672?.revision||0}});
  assert(saved.ok());
  await page.goto('http://127.0.0.1:8768/');
  await page.getByRole('button',{name:'Phân tích lỗi',exact:true}).click({timeout:5000});
  await page.getByRole('heading',{name:'Agent lệch ở bước nào?'}).waitFor();
  assert.equal(await page.locator('[data-analysis-group]').count(),17);
  const writes=[];page.on('request',r=>{if(r.method()==='PUT')writes.push(r.url())});
  await page.locator('.analysis-detail').getByText('Current review differs from pilot',{exact:true}).waitFor();
  await page.locator('[data-analysis-group="M10"]').click();
  await page.locator('[data-analysis-sample="train_1697"]').click();
  await page.locator('.analysis-detail details').filter({hasText:'Lượt 1 · reasoning'}).locator('summary').click();
  assert((await page.locator('.analysis-detail').innerText()).includes('lock_id'));
  const search=page.getByRole('textbox',{name:'Tìm nhóm hoặc sample',exact:true});
  await search.fill('does-not-exist');
  await page.getByText('Không có sample phù hợp bộ lọc.',{exact:true}).waitFor();
  assert.equal(await page.locator('.analysis-detail h2').count(),0);
  await search.fill('train_0454');
  await page.locator('.analysis-detail h2').filter({hasText:'train_0454'}).waitFor();
  await search.fill('');
  await page.getByRole('combobox',{name:'Lọc lớp phân tích',exact:true}).selectOption('P');
  assert.equal(await page.locator('[data-analysis-group]').count(),1);
  await page.locator('[data-analysis-sample="train_0672"]').click();
  await page.screenshot({path:'logs/analysis-integrated.png',fullPage:true});
  // Existing review draft must survive cancelled navigation from the analysis tab.
  await page.getByRole('button',{name:'Review sample',exact:true}).click();
  await page.locator('#comment').fill('Unsaved draft must survive');
  await page.getByRole('button',{name:'Phân tích lỗi',exact:true}).click();
  page.once('dialog',d=>d.dismiss());
  await page.getByRole('button',{name:'Mở trong Review sample →',exact:true}).click();
  await page.getByRole('heading',{name:'Agent lệch ở bước nào?'}).waitFor();
  await page.getByRole('button',{name:'Review sample',exact:true}).click();
  assert.equal(await page.locator('#comment').inputValue(),'Unsaved draft must survive');
  await page.getByRole('button',{name:'Phân tích lỗi',exact:true}).click();
  page.once('dialog',d=>d.accept());
  await page.getByRole('button',{name:'Mở trong Review sample →',exact:true}).click();
  await page.getByRole('heading',{name:'train_0672',exact:true}).waitFor();
  assert.equal(await page.locator('#comment').inputValue(),'Current review differs from pilot');
  assert.deepEqual(writes,[]);
  // Missing/foreign analysis must not break other tabs; manipulate disposable files only.
  const path='logs/analysis-ui-test-data/error_analysis.json',original=fs.readFileSync(path);
  try{
   fs.renameSync(path,path+'.test-backup');
   await page.getByRole('button',{name:'Phân tích lỗi',exact:true}).click();
   await page.getByText(/Chưa có dữ liệu phân nhóm/).waitFor();
   fs.writeFileSync(path,JSON.stringify({...JSON.parse(original),experiment:'foreign'}));
   await page.getByRole('button',{name:'Thử tải lại',exact:true}).click();
   await page.getByRole('alert').filter({hasText:'another experiment'}).waitFor();
   await page.getByRole('button',{name:'Tổng quan',exact:true}).click();
   await page.getByRole('heading',{name:'Tổng quan',exact:true}).waitFor();
  }finally{fs.writeFileSync(path,original);if(fs.existsSync(path+'.test-backup'))fs.unlinkSync(path+'.test-backup')}
  assert.deepEqual(errors,[]);
  console.log('PASS analysis navigation, evidence, filters, current review, draft guard, no writes, missing/foreign data.');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
