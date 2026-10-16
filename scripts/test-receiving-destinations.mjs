/* global document, innerWidth */
/** Exercises real Receiving forms against synthetic API fixtures only. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {writeFile,unlink,mkdir} from 'node:fs/promises';
import {chromium} from 'playwright-core';
const root=process.cwd(), stem=`.qa-receiving-${process.pid}`,port=5198;
const files=[`${root}/${stem}.html`,`${root}/${stem}.tsx`];
let server,browser;
const products=[
 {id:1,code:'1-800100',name:'READY MEAL',uom:'PAX',inventory_treatment:'DIRECT_USE',catalog_type:'HOTEL',purchase_account_id:37,reference_cost:25000,is_taxable:false,tax_rate:0},
 {id:2,code:'1-100004',name:'FROZEN BEEF',uom:'KG',inventory_treatment:'STOCK',catalog_type:'HOTEL',purchase_account_id:37,reference_cost:120000,is_taxable:false,tax_rate:0},
];
const po={id:10,po_number:'PO-QA',business_unit_id:8,business_unit_name:'Hotel',location_id:8,location_name:'Hotel',department_id:7,department_name:'Food and Beverage'};
const items=products.map((p,i)=>({...p,purchase_order_item_id:i+1,product_id:p.id,product_code:p.code,product_name:p.name,ordered_quantity:5,received_quantity:0,remaining_quantity:5,unit_cost:p.reference_cost}));
const receipt={id:20,receipt_number:'GR-QA',destination_type:'MIXED',status:'DRAFT',source_type:'LIVE',business_unit_id:8,department_id:7,location_id:8,warehouse_id:5,received_at:'2026-10-16T03:00:00Z',items:items.map((p,i)=>({...p,id:i+1,quantity:2,destination_type:i?'WAREHOUSE':'DIRECT_USE',expense_account_id:i?null:37}))};
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try{
 await writeFile(files[0],`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/${stem}.tsx"></script></body></html>`);
 await writeFile(files[1],`import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClientProvider,QueryClient}from'@tanstack/react-query';import Direct from'./src/modules/purchasing/goods-receipts/components/DirectReceiveDialog';import PO from'./src/modules/purchasing/goods-receipts/components/ReceiveGoodsDialog';import Edit from'./src/modules/purchasing/goods-receipts/components/EditReceivingDialog';import useAuth from'./src/store/auth';import './src/styles/index.css';useAuth.setState({user:{id:1,username:'qa',full_name:'QA Administrator',roles:[{name:'SYSTEM_ADMINISTRATOR'}]},loading:false,authenticated:true});const mode=new URLSearchParams(location.search).get('mode');const client=new QueryClient({defaultOptions:{queries:{retry:false}}});createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}><MemoryRouter>{mode==='po'?<PO open purchaseOrder={${JSON.stringify(po)}} onClose={()=>{}}/>:mode==='edit'?<Edit open receipt={${JSON.stringify(receipt)}} onClose={()=>{}}/>:<Direct open onClose={()=>{}}/>}</MemoryRouter></QueryClientProvider>);`);
 server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:root,stdio:'pipe'});
 await Promise.race([new Promise((resolve,reject)=>{server.stdout.on('data',b=>String(b).includes('Local:')&&resolve());server.once('exit',c=>reject(Error(`Vite exited ${c}`)))}),pause(20000).then(()=>{throw Error('Vite startup timed out')})]);
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],writes=[],unmocked=[];page.setDefaultTimeout(10000);page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',route=>{
  const r=route.request();if(!['xhr','fetch'].includes(r.resourceType()))return route.continue();const url=new URL(r.url()),p=url.pathname;let data;
  if(r.method()!=='GET'){assert.match(p,/goods-receipts/);writes.push(r.postDataJSON());data=receipt;}
  else if(p.endsWith('/business-units'))data=[{id:8,code:'HOTEL',name:'Hotel',is_active:true}];
  else if(p.endsWith('/locations'))data=[{id:8,code:'HOTEL',name:'Hotel',business_unit_id:8,is_active:true}];
  else if(p.endsWith('/departments'))data=[{id:7,code:'FB',name:'Food and Beverage',business_unit_id:8,is_active:true}];
  else if(p.endsWith('/warehouses'))data=[{id:5,code:'WH-HOTEL',name:'Hotel Warehouse',location_id:8,is_active:true},{id:6,code:'WH-OTHER',name:'Other Location',location_id:1,is_active:true}];
  else if(p.includes('/suppliers'))data=[{id:1,code:'SUP',name:'Test Supplier'}];
  else if(p.includes('/products'))data=products;
  else if(p.endsWith('/chart-of-accounts/lookup'))data=[{id:37,account_code:'500-100-100',account_name:'Food Cost'}];
  else if(p.endsWith('/receivable-purchase-orders/10/items'))data=items;
  else{unmocked.push(p);return route.fulfill({status:404,body:'Unmocked request blocked'});}
  return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });
 const assertCompact=async()=>{const table=page.locator('table.receiving-lines');const metrics=await table.evaluate(t=>({table:t.getBoundingClientRect().width,available:t.parentElement.clientWidth,qty:t.querySelector('col.rl-quantity').getBoundingClientRect().width,unit:t.querySelector('col.rl-unit').getBoundingClientRect().width,tax:t.querySelector('col.rl-tax-rate').getBoundingClientRect().width}));assert.ok(metrics.table<=metrics.available+1,`Receiving fits desktop: ${JSON.stringify(metrics)}`);assert.ok(metrics.qty<=80&&metrics.unit<=48&&metrics.tax<=68,`Compact numeric columns: ${JSON.stringify(metrics)}`);};
 const goto=mode=>page.goto(`http://127.0.0.1:${port}/${stem}.html?mode=${mode}`);
 const choose=async(placeholder,text)=>{await page.getByPlaceholder(placeholder,{exact:true}).fill(text);await page.locator('button[role=option]').filter({hasText:text}).first().click();};
 await goto('direct');await page.getByRole('dialog').waitFor();await assertCompact();await page.setViewportSize({width:1280,height:900});await assertCompact();await page.setViewportSize({width:1440,height:1000});
 assert.equal(await page.locator('label').filter({hasText:/^Destination$/}).count(),0,'No document-wide destination selector');
 await choose('Type supplier code or name...','Test Supplier');await choose('Type business unit...','Hotel');await choose('Type location...','Hotel');await choose('Type department...','Food and Beverage');
 await page.getByPlaceholder('Type product code or name...').fill('READY MEAL');await page.getByRole('option').filter({hasText:'READY MEAL'}).click();
 assert.equal(await page.getByPlaceholder('Type warehouse code or name...').count(),0,'Direct Use needs no warehouse');
 assert.match(await page.locator('tbody').innerText(),/Direct Use/);
 await page.getByRole('button',{name:'Save RR Draft',exact:true}).click();await page.waitForFunction(()=>true);await pause(200);
 assert.equal(writes.length,1);assert.equal(writes[0].destination_type,undefined);assert.equal(writes[0].warehouse_id,null);assert.equal(writes[0].items[0].destination_type,null);assert.equal(writes[0].items[0].expense_account_id,37);
 await page.getByRole('button',{name:'Add Item',exact:true}).click();await page.getByPlaceholder('Type product code or name...').last().fill('FROZEN BEEF');await page.getByRole('option').filter({hasText:'FROZEN BEEF'}).click();
 await page.getByPlaceholder('Type warehouse code or name...').waitFor();await choose('Type warehouse code or name...','Hotel Warehouse');
 await page.getByRole('button',{name:'Destination options for READY MEAL',exact:true}).click();await page.getByLabel('Destination for READY MEAL',{exact:true}).selectOption('WAREHOUSE');
 const alertText=[];page.on('dialog',async dialog=>{alertText.push(dialog.message());await dialog.dismiss();});
 await page.getByRole('button',{name:'Save RR Draft',exact:true}).click();assert.equal(writes.length,1);assert.match(alertText.at(-1),/reason/);
 await page.getByLabel('Destination reason for READY MEAL',{exact:true}).fill('Special batch held for later use');
 await page.getByRole('button',{name:'Save RR Draft',exact:true}).click();await pause(200);
 await assertCompact();
 if(process.env.QA_SCREENSHOT_DIR){await mkdir(process.env.QA_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:`${process.env.QA_SCREENSHOT_DIR}/receiving-create.png`});}
 assert.equal(writes.length,2);assert.equal(writes[1].items[0].destination_type,'WAREHOUSE');assert.equal(writes[1].items[0].expense_account_id,null);assert.equal(writes[1].items[1].destination_type,null);assert.equal(writes[1].warehouse_id,5);
 await goto('po');await page.getByRole('columnheader',{name:'Destination',exact:true}).waitFor();assert.match(await page.locator('tbody').innerText(),/Direct Use/);assert.match(await page.locator('tbody').innerText(),/Warehouse/);
 await page.setViewportSize({width:1280,height:900});await assertCompact();await page.setViewportSize({width:1440,height:1000});
 await page.getByRole('spinbutton').nth(0).fill('2');await page.getByRole('spinbutton').nth(2).fill('2');await choose('Type warehouse code or name...','Hotel Warehouse');await page.getByRole('button',{name:'Save Receiving Draft',exact:true}).click();await pause(200);if(process.env.QA_SCREENSHOT_DIR)await page.screenshot({path:`${process.env.QA_SCREENSHOT_DIR}/receiving-po.png`});assert.equal(writes.length,3);assert.equal(writes[2].purchase_order_id,10);assert.equal(writes[2].destination_type,undefined);
 await goto('edit');await page.getByRole('columnheader',{name:'Destination',exact:true}).waitFor();assert.match(await page.locator('tbody').innerText(),/Direct Use/);assert.match(await page.locator('tbody').innerText(),/Warehouse/);await page.getByRole('button',{name:'Save Changes',exact:true}).click();await pause(200);assert.equal(writes.length,4);assert.deepEqual(writes[3].items.map(x=>x.destination_type),['DIRECT_USE','WAREHOUSE']);
 await page.setViewportSize({width:1280,height:900});await assertCompact();await page.setViewportSize({width:1440,height:1000});
 if(process.env.QA_SCREENSHOT_DIR){await mkdir(process.env.QA_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:`${process.env.QA_SCREENSHOT_DIR}/receiving-desktop.png`});await page.setViewportSize({width:390,height:844});await page.screenshot({path:`${process.env.QA_SCREENSHOT_DIR}/receiving-mobile.png`});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);}
 assert.deepEqual(unmocked,[]);assert.deepEqual(errors,[]);console.log('PASS: Item Master defaults, no header selector, per-line exceptions/reason, warehouse scope, Direct/PO/Edit payloads, compact columns fit 1280/1440 desktop, mobile contained scrolling, synthetic writes only.');
}finally{await browser?.close();server?.kill();await Promise.all(files.map(f=>unlink(f).catch(()=>{})));}
