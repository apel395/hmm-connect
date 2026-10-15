/** Real components with synthetic read-only API fixtures; no production requests. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {writeFile,unlink,mkdir} from 'node:fs/promises';
import {chromium} from 'playwright-core';
const root=process.cwd(),suffix=`.qa-workspaces-${process.pid}`,port=5194,pause=ms=>new Promise(r=>setTimeout(r,ms));
let server,browser;
const paths={products:'src/modules/master/products/pages/ProductPage',suppliers:'src/modules/master/suppliers/pages/SupplierPage',warehouses:'src/modules/master/warehouses/WarehousePage',organization:'src/modules/admin/organization/OrganizationDimensionsPage',accounts:'src/modules/master/chart-of-accounts/pages/ChartOfAccountPage',movements:'src/modules/warehouse/inventory/pages/InventoryMovementPage',requests:'src/modules/warehouse/store-request/StoreRequestPage',opnames:'src/modules/warehouse/stock-opname/StockOpnamePage',adjustments:'src/modules/warehouse/inventory-adjustment/pages/StockAdjustmentPage',stockcard:'src/modules/warehouse/stock-card/StockCardPage',inventoryReports:'src/modules/warehouse/inventory/pages/InventoryReportsPage',journal:'src/modules/finance/journals/JournalWorkspacePage',ledger:'src/modules/finance/general-ledger/GeneralLedgerPage',trial:'src/modules/finance/trial-balance/TrialBalancePage',balance:'src/modules/finance/financial-statements/BalanceSheetPage',profit:'src/modules/finance/financial-statements/ProfitLossPage'};
const products=Array.from({length:80},(_,i)=>({id:i+1,code:`1-${500001+i}`,name:`FRESH VEGETABLE ${i+1}`,item_type:'BUY',catalog_type:'CATERING',group_name:'FOOD',subgroup_name:'VEGETABLES',inventory_treatment:'STOCK',is_active:true,uom:'KG',usage_uom:'KG',conversion:1,reference_cost:25000,cost_price:25000,tax_category:'NON_TAXABLE',is_taxable:false,tax_rate:0,inventory_account_id:1}));
const accounts=Array.from({length:45},(_,i)=>({id:i+1,account_id:i+1,account_code:`100-300-${100+i}`,account_number:`100-300-${100+i}`,account_name:`Inventory account ${i+1}`,account_type:'ASSET',normal_balance:'DEBIT',is_active:true,is_posting:true,account_subtype:'OTHER',opening_balance:'1000.00',prior_debit:'0.00',prior_credit:'0.00',period_debit:'250.00',period_credit:'0.00',closing_balance:'1250.00',status:i===2?'ABNORMAL':'NORMAL'}));
const units=[{id:1,code:'HOTEL',name:'Hotel',is_active:true},{id:2,code:'CATERING',name:'Project Catering',is_active:true}];
const locations=[{id:8,code:'HOTEL',name:'Hotel Pekanbaru',business_unit_id:1,is_active:true,department_ids:[7],location_type:'SITE'}];
const warehouses=Array.from({length:50},(_,i)=>({id:i+1,code:`WH-${String(i+1).padStart(3,'0')}`,name:`Warehouse ${i+1}`,location_id:8,is_active:true}));
const suppliers=Array.from({length:50},(_,i)=>({id:i+1,code:`SUP-${i+1}`,name:`Supplier ${i+1}`,is_active:true,is_pkp:false,rows:[]}));
const journals=Array.from({length:50},(_,i)=>({id:i+1,journal_number:`MAN-202610-${100+i}`,journal_date:'2026-10-15',reference_type:'MANUAL',reference_number:`DOC-${i+1}`,description:`Operational transaction ${i+1}`,status:'POSTED',total_debit:25000,total_credit:25000,allowed_actions:{can_copy:true}}));
const ledger=Array.from({length:50},(_,i)=>({id:i+1,posting_date:'2026-10-15',journal_id:i+1,journal_number:`MAN-202610-${100+i}`,account_name:'Inventory Food',description:`Receiving ${i+1}`,reference_number:`GR-${i+1}`,debit:25000,credit:0,balance:(i+1)*25000,location_name:'Hotel',department_name:'Food & Beverage'}));
const movements=Array.from({length:50},(_,i)=>({id:i+1,movement_date:'2026-10-15',movement_type:i%2?'OUT':'IN',product_id:i+1,product_code:products[i].code,product_name:products[i].name,warehouse_id:1,warehouse_name:'Main warehouse',quantity:5,in_quantity:i%2?0:5,out_quantity:i%2?5:0,running_quantity:50-i,unit_cost:25000,movement_value:125000,reference_type:'GOODS_RECEIPT',reference_number:`GR-${i+1}`,goods_receipt_id:600+i,receipt_number:`GR-${i+1}`}));
const amounts={current:'1250.00',budget:null,last_month:'1000.00',last_year:'0.00',variance:null,movement:'250.00'};
const periods={MTD:amounts,YTD:amounts};
function report(url){const pl=url.searchParams.get('report_type')==='PROFIT_LOSS',unit=Number(url.searchParams.get('business_unit_id'))||null;return{rows:accounts.map((a,i)=>({...a,account_ids:[a.id],section:i<25?'ASSETS':i<35?'LIABILITIES':'EQUITY',periods})),scope:{location_id:null,business_unit_id:unit,department_id:null},scope_labels:{business_unit_id:units.find(x=>x.id===unit)?.name},periods:{MTD:{current:['2026-10-01','2026-10-15']},YTD:{current:['2026-01-01','2026-10-15']}},section_totals:Object.fromEntries(['ASSETS','LIABILITIES','EQUITY','REVENUE','COST_OF_REVENUE','EXPENSES'].map(s=>[s,{MTD:amounts,YTD:amounts}])),presentation_rows:pl?['REVENUE','COST_OF_REVENUE','OPERATIONAL_SALARY','OPERATIONAL_EXPENSE','GOI','OVERHEAD_SALARY','OVERHEAD_EXPENSE','GOP','UNDER_EXPENSE','NOP'].map(key=>({key,label:key.replaceAll('_',' '),kind:['GOI','GOP','NOP'].includes(key)?'subtotal':'category',account_ids:[1,2],periods})):undefined,related_accounts:[{account_id:1,account_code:'400',account_name:'Sales revenue',category:'REVENUE',periods},{account_id:2,account_code:'400-ZERO',account_name:'Zero value related account',category:'REVENUE',periods:{MTD:{...amounts,current:'0.00'},YTD:{...amounts,current:'0.00'}}}]};}
function paginate(rows,url,extras={}){const size=Number(url.searchParams.get('page_size')||50),page=Number(url.searchParams.get('page')||1),search=(url.searchParams.get('search')||'').toLowerCase();const filtered=search?rows.filter(r=>JSON.stringify(r).toLowerCase().includes(search)):rows;return{items:filtered.slice((page-1)*size,page*size),total_items:filtered.length,total_pages:Math.ceil(filtered.length/size),page,page_size:size,has_next:page*size<filtered.length,has_previous:page>1,...extras};}
try{
 await writeFile(`${root}/${suffix}.html`,`<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/${suffix}.tsx"></script></body></html>`);
 await writeFile(`${root}/${suffix}.tsx`,`import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter,Routes,Route}from'react-router-dom';import{QueryClientProvider,QueryClient}from'@tanstack/react-query';import AppLayout from'./src/layouts/AppLayout';import useAuth from'./src/store/auth';import './src/styles/index.css';${Object.entries(paths).map(([key,path])=>`import ${key} from './${path}';`).join('')}const pages={${Object.keys(paths).join(',')}};const view=new URLSearchParams(window.location.search).get('view')||'products';const Page=pages[view];useAuth.setState({user:{id:1,full_name:'QA Administrator',username:'qa',roles:[{name:'SYSTEM_ADMINISTRATOR'}]},loading:false,authenticated:true});const client=new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}});createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/qa']}><Routes><Route element={<AppLayout/>}><Route path="qa" element={view==='journal'?<Page section="journal"/>:<Page/>}/></Route></Routes></MemoryRouter></QueryClientProvider>);`);
 server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:root,stdio:'pipe'});
 await Promise.race([new Promise((res,rej)=>{server.stdout.on('data',d=>{if(String(d).includes('Local:'))res()});server.once('exit',c=>rej(Error(`Vite exited ${c}`)));}),pause(20000).then(()=>{throw Error('Vite timeout')})]);
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];page.setDefaultTimeout(12000);page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',route=>{const req=route.request();if(!['fetch','xhr'].includes(req.resourceType()))return route.continue();assert.equal(req.method(),'GET');const u=new URL(req.url()),p=u.pathname;requests.push(u);let body;
 if(p.endsWith('/products/classification-master'))body=[];
 else if(p.endsWith('/products'))body=paginate(products,u);
 else if(/\/products\/\d+$/.test(p))body={...products[0],purchase_history:[],stock:[]};
 else if(p.endsWith('/chart-of-accounts/lookup'))body=accounts;
 else if(p.endsWith('/chart-of-accounts/tree'))body=[];
 else if(p.endsWith('/chart-of-accounts'))body=paginate(accounts,u);
 else if(p.endsWith('/inventory/accounts'))body=accounts.slice(0,1);
 else if(p.endsWith('/business-units'))body=units;
 else if(p.endsWith('/locations'))body=locations;
 else if(p.endsWith('/departments'))body=[{id:7,name:'Food and Beverage',code:'FB',is_active:true,business_unit_id:1}];
 else if(p.endsWith('/warehouses'))body=warehouses;
 else if(p.endsWith('/suppliers/lookup'))body=suppliers;
 else if(p.endsWith('/suppliers'))body=paginate(suppliers,u);
 else if(p.endsWith('/journal-entries/scope'))body={units,locations,location_locked:false,default_location_id:null,default_business_unit_id:null};
 else if(p.endsWith('/journal-entries'))body=paginate(journals,u,{summary:{total_debit:1250000,total_credit:1250000},totals:{debit:1250000,credit:1250000},total_debit:1250000,total_credit:1250000});
 else if(p.endsWith('/general-ledger'))body=paginate(ledger,u,{summary:{total_debit:1250000,total_credit:0},totals:{debit:1250000,credit:0}});
 else if(p.endsWith('/trial-balance'))body=paginate(accounts,u,{summary:{}});
 else if(p.endsWith('/financial-reports/comparison'))body=report(u);
 else if(p.endsWith('/financial-reports/comparison/export'))return route.fulfill({contentType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',body:'QA export'});
 else if(p.endsWith('/budgets'))body={items:[]};
 else if(p.endsWith('/inventory/movements'))body=paginate(movements,u,{summary:{in_value:3125000,out_value:3125000,out_qty:125},totals_by_account:[]});
 else if(p.endsWith('/store-requests'))body=paginate(journals.map((r,i)=>({...r,sr_number:`SR-${i+1}`,request_date:'2026-10-15',requester_name:'Warehouse user',warehouse_name:'Main warehouse',department_name:'F&B',remaining_quantity:2})),u);
 else if(p.endsWith('/stock-opnames'))body=paginate(journals.map((r,i)=>({...r,opname_number:`SO-${i+1}`,count_date:'2026-10-15',warehouse_name:'Main warehouse',location_name:'Hotel',total_items:10,blind_count:true,total_variance_quantity:999})),u,{blind_count:true});
 else if(p.endsWith('/stock-adjustments'))body=paginate(journals.map((r,i)=>({...r,adjustment_number:`ADJ-${i+1}`,adjustment_date:'2026-10-15',warehouse_name:'Main warehouse',warehouse_code:'WH-001',reason:'Count adjustment',total_adjustment_value:25000,created_by_name:'QA'})),u,{status_counts:{DRAFT:0,POSTED:50,VOID:0}});
 else if(p.endsWith('/inventory/stock-card'))body=paginate(movements,u,{totals_by_account:[]});
 else if(p.endsWith('/inventory'))body={...paginate(products,u),summary:{stock_lines:80,stock_value:2000000,monitored_lines:80,low_stock:0},totals_by_account:accounts.map(a=>({...a,quantity:100,stock_value:2500000}))};
 else return route.fulfill({status:404,body:'Unmocked API blocked'});
 return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
 });
 const go=async view=>{await page.goto(`http://127.0.0.1:${port}/${suffix}.html?view=${view}`);await page.locator('.data-workspace').waitFor();await pause(500);};
 for(const view of ['products','suppliers','warehouses','organization','accounts','movements','requests','opnames','adjustments','stockcard','inventoryReports','journal','ledger','trial','balance','profit']){
  await page.setViewportSize({width:1440,height:1000});await go(view);
  const tables=page.locator('.workspace-data table,.workspace-report-table table,.workspace-profit-table table');await tables.first().waitFor();assert.ok(await tables.first().locator('tbody tr').count()>0,`${view} fixture rows must render`);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${view} desktop overflow`);
  const viewport=page.locator('.workspace-data [data-table-viewport],.workspace-data .workspace-table-scroll,.workspace-data.workspace-table-scroll,.workspace-report-table,.workspace-profit-table').first();
  if(!['inventoryReports','stockcard'].includes(view))assert.ok((await viewport.boundingBox()).height>350,`${view} table must dominate workspace`);
  if(view==='opnames')assert.equal(await page.getByRole('columnheader',{name:'Variance',exact:true}).count(),0,'Blind count must hide variance');
  if(['products','journal','ledger','trial'].includes(view)){
   const head=tables.first().locator('thead th').first(),y=await head.evaluate(el=>el.getBoundingClientRect().top);
   await viewport.evaluate(el=>el.scrollTop=400);assert.ok(Math.abs(y-await head.evaluate(el=>el.getBoundingClientRect().top))<1,`${view} frozen header`);
   await viewport.evaluate(el=>el.scrollTop=0);
  }
  if(view==='products'){
   assert.equal(await page.getByRole('columnheader',{name:'Item code',exact:true}).count(),1);assert.equal(await page.getByRole('columnheader',{name:'Item name',exact:true}).count(),1);
   await page.getByRole('button',{name:'Extra compact rows',exact:true}).click();assert.equal(await page.locator('.data-workspace').getAttribute('data-density'),'dense');
   await page.reload();await page.getByRole('columnheader',{name:'Item code',exact:true}).waitFor();assert.equal(await page.locator('.data-workspace').getAttribute('data-density'),'dense');
   await page.getByPlaceholder('Search item code or name...').fill('VEGETABLE 3');await pause(500);assert.ok(requests.some(u=>u.pathname.endsWith('/products')&&u.searchParams.get('search')==='VEGETABLE 3'));
  }
  if(view==='profit'){
   await page.getByRole('button',{name:'Show accounts for REVENUE',exact:true}).click();await page.getByRole('dialog').waitFor();assert.match(await page.getByRole('dialog').innerText(),/Zero value related account/);await page.getByRole('button',{name:'Close',exact:true}).click();
   await page.getByRole('button',{name:'Hotel',exact:true}).click();await pause(150);assert.ok(requests.some(u=>u.pathname.endsWith('/financial-reports/comparison')&&u.searchParams.get('business_unit_id')==='1'));
   await page.getByRole('button',{name:'YTD',exact:true}).click();assert.equal(await page.getByRole('columnheader',{name:'YTD',exact:true}).count(),1);
  }
  if(process.env.QA_SCREENSHOT_DIR&&['products','movements','journal','ledger','trial','balance','profit'].includes(view)){await mkdir(process.env.QA_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:`${process.env.QA_SCREENSHOT_DIR}/${view}-desktop.png`});}
  await page.setViewportSize({width:390,height:844});await pause(100);assert.ok((await page.locator('.workspace-page-header h1').first().boundingBox()).height<30,`${view} mobile title must stay on one line`);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,`${view} mobile overflow`);
  if(process.env.QA_SCREENSHOT_DIR&&['products','balance','ledger'].includes(view))await page.screenshot({path:`${process.env.QA_SCREENSHOT_DIR}/${view}-mobile.png`});
  await page.emulateMedia({media:'print'});assert.equal(await page.locator('.data-workspace').evaluate(el=>getComputedStyle(el).overflow),'visible',`${view} print clipping`);await page.emulateMedia({media:'screen'});
  console.log(`PASS ${view}: workspace, desktop/mobile, print${view==='opnames'?', blind count':''}`);
 }
 assert.deepEqual(errors,[]);console.log('PASS: dense preference, frozen headers, separate item columns, report scope, zero-account drilldown, no writes.');
}finally{await browser?.close();server?.kill();await Promise.all([unlink(`${root}/${suffix}.html`).catch(()=>{}),unlink(`${root}/${suffix}.tsx`).catch(()=>{})]);}
