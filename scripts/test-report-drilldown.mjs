/* global innerWidth, innerHeight */
/** Real P&L table/dialog; synthetic data only, no signed-in session or API. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {writeFile,unlink,mkdir} from 'node:fs/promises';
import {chromium} from 'playwright-core';
const root=process.cwd(),stem=`.qa-report-${process.pid}`,port=5197;
const files=[`${root}/${stem}.html`,`${root}/${stem}.tsx`];
let server,browser;
const amount={current:'123456',budget:null,last_month:'100000',last_year:null,variance:null};
const periods={MTD:amount,YTD:amount};
const accounts=Array.from({length:80},(_,i)=>({account_id:i+1,account_code:`700-500-${i+100}`,account_name:`Operating expense account ${i+1}`,category:'OPERATING_EXPENSE',periods}));
const report={scope:{location_id:8,business_unit_id:1,department_id:7},related_accounts:accounts,presentation_rows:[{key:'OPERATING_EXPENSE',label:'Beban operasional',kind:'category',account_ids:accounts.map(a=>a.account_id),periods}]};
try{
 await writeFile(files[0],`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/${stem}.tsx"></script></body></html>`);
 await writeFile(files[1],`import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import Table from'./src/modules/finance/financial-statements/ProfitLossTable';import'./src/styles/index.css';createRoot(document.getElementById('root')!).render(<MemoryRouter><Table data={${JSON.stringify(report)} as any} periods={['MTD','YTD']} asOf="2026-10-16"/></MemoryRouter>);`);
 server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:root,stdio:'pipe'});
 await Promise.race([new Promise((resolve,reject)=>{server.stdout.on('data',b=>String(b).includes('Local:')&&resolve());server.once('exit',c=>reject(Error(`Vite exited ${c}`)))}),new Promise((_,reject)=>setTimeout(()=>reject(Error('Vite startup timed out')),20000))]);
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 const page=await browser.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 for(const size of [{width:1920,height:1080},{width:1440,height:900},{width:1280,height:800},{width:390,height:844}]){
  await page.setViewportSize(size);
  await page.goto(`http://127.0.0.1:${port}/${stem}.html`);
  await page.getByRole('button',{name:'Show accounts for Beban operasional'}).click();
  const dialog=page.getByRole('dialog');await dialog.waitFor();
  const geometry=await dialog.evaluate(d=>{const r=d.getBoundingClientRect();return{x:r.x,y:r.y,w:r.width,h:r.height,vw:innerWidth,vh:innerHeight};});
  assert.ok(Math.abs(geometry.x+geometry.w/2-size.width/2)<2,`Horizontally centered ${JSON.stringify(geometry)}`);
  assert.ok(Math.abs(geometry.y+geometry.h/2-size.height/2)<2,`Vertically centered ${JSON.stringify(geometry)}`);
  assert.ok(geometry.x>=0&&geometry.y>=0&&geometry.w<=size.width&&geometry.h<=size.height);
  if(size.width>=1280)assert.ok(geometry.w>=1200,'Wide desktop popup');
  assert.equal(await dialog.locator('tbody tr').count(),80);
  const link=new URL(await dialog.locator('tbody a').first().getAttribute('href'),'https://example.test');
  for(const [key,value] of Object.entries({account_id:'1',date_from:'2026-10-01',date_to:'2026-10-16',location_id:'8',business_unit_id:'1',department_id:'7'}))assert.equal(link.searchParams.get(key),value);
  const scroll=dialog.locator('div.overflow-auto');await scroll.evaluate(d=>{d.scrollTop=500;});
  const head=await dialog.locator('thead').boundingBox(),body=await scroll.boundingBox();
  assert.ok(Math.abs(head.y-body.y)<2,'Header stays visible when scrolling');
  const codeHead=await dialog.getByRole('columnheader',{name:'Code',exact:true}).boundingBox();
  assert.ok(codeHead.y>=head.y-1&&codeHead.y+codeHead.height<=head.y+head.height+1,'Code heading stays in the sticky header');
  if(process.env.QA_SCREENSHOT_DIR){await mkdir(process.env.QA_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:`${process.env.QA_SCREENSHOT_DIR}/report-drilldown-${size.width}.png`});}
  await page.keyboard.press('Escape');await dialog.waitFor({state:'hidden'});
 }
 assert.deepEqual(errors,[]);
 console.log('PASS: centered wide popup at 1920/1440/1280, bounded mobile dialog, 80 accounts, sticky headers, scope/date-safe GL links and Escape close.');
}finally{await browser?.close();server?.kill();await Promise.all(files.map(f=>unlink(f).catch(()=>{})));}
