const {chromium}=require('../.superpowers/review-browser-check/node_modules/playwright');
const assert=require('node:assert/strict');
(async()=>{
 const b=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 const p=await b.newPage();await p.goto('http://127.0.0.1:8766');await p.locator('#comment').waitFor();
 const id=await p.locator('main h1').textContent();
 let release;const gate=new Promise(r=>release=r);let reached;const seen=new Promise(r=>reached=r);
 await p.route('**/api/review/**',async route=>{reached();await gate;await route.continue()});
 await p.locator('#comment').fill('delayed save origin');
 await p.locator('.review button').click();await seen;
 assert.equal(await p.locator('#comment').isDisabled(),true,'Draft must be disabled during save');
 const buttons=p.locator('button.sample');await buttons.nth(1).click();
 assert.equal(await p.locator('main h1').textContent(),id,'Navigation must wait for save');
 release();await p.getByRole('status').filter({hasText:'Đã lưu vào SQLite'}).waitFor();
 await b.close();console.log('PASS: delayed save locks draft and sample navigation');
})().catch(e=>{console.error(e.message);process.exit(1)});
