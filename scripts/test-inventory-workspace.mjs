/** Browser regression using synthetic stock only. No production API requests or writes. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {writeFile,unlink} from 'node:fs/promises';
import {chromium} from 'playwright-core';
const root=process.cwd(), suffix=`.qa-stock-${process.pid}`, port=5193;
const html=`${root}/${suffix}.html`,entry=`${root}/${suffix}.tsx`;
let server,browser;
const names=['BEEF SAUSAGE','BEEF BALL','BEEF KNUCKLE LOKAL','CHICKEN SAUSAGE','CHICKEN BREAST FILLET','TENDERLOIN LOCAL','MIXED VEGETABLES FROZEN','FRESH TOMATO','RED ONION','CARROT','POTATO','GREEN CHILLI','FRESH MILK','MINERAL WATER','ORANGE JUICE','WHEAT FLOUR','COOKING OIL','RICE PREMIUM','WHITE SUGAR','BUTTER UNSALTED'];
const rows=Array.from({length:80},(_,i)=>({id:i+1,product_id:100+i,product_code:`1-${100001+i}`,product_name:names[i%20]+(i>=20?` ${Math.floor(i/20)+1}`:''),uom:i%5?'KG':'PCK',warehouse_id:5,warehouse_code:'WH-005',warehouse_name:'Rumin',quantity:i%9===0?0:i%7===0?2:5+i,average_cost:59069+i*320,stock_value:(i%9===0?0:i%7===0?2:5+i)*(59069+i*320),minimum_stock:3,low_stock:i%9===0||i%7===0,shortage:0,inventory_account_code:'100-300-100',inventory_account_name:'Inv Makanan'}));
const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
try{
 await writeFile(html,`<!doctype html><html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/${suffix}.tsx"></script></body></html>`);
 await writeFile(entry,`import React from 'react';import{createRoot}from'react-dom/client';import{MemoryRouter,Routes,Route}from'react-router-dom';import{QueryClientProvider,QueryClient}from'@tanstack/react-query';import AppLayout from'./src/layouts/AppLayout';import InventoryPage from'./src/modules/warehouse/inventory/pages/InventoryPage';import useAuth from'./src/store/auth';import './src/styles/index.css';useAuth.setState({user:{id:1,full_name:'QA Administrator',username:'qa-stock',roles:[{name:'SYSTEM_ADMINISTRATOR'}]},loading:false,authenticated:true});const client=new QueryClient({defaultOptions:{queries:{retry:false,refetchOnWindowFocus:false}}});createRoot(document.getElementById('root')!).render(<QueryClientProvider client={client}><MemoryRouter initialEntries={['/inventory'+window.location.search]}><Routes><Route element={<AppLayout/>}><Route path="inventory" element={<InventoryPage/>}/><Route path="inventory/movements" element={<p>Stock card destination</p>}/></Route></Routes></MemoryRouter></QueryClientProvider>);`);
 server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:root,stdio:'pipe'});
 await Promise.race([new Promise((resolve,reject)=>{server.stdout.on('data',d=>{if(String(d).includes('Local:'))resolve()});server.once('exit',code=>reject(new Error(`Vite exited ${code}`)));}),pause(20000).then(()=>{throw new Error('Vite startup timed out')})]);
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[],requests=[];page.setDefaultTimeout(10000);
 page.on('pageerror',error=>errors.push(error.message));
 await page.route('**/*',route=>{
  const request=route.request();if(!['xhr','fetch'].includes(request.resourceType()))return route.continue();
  const url=new URL(request.url()),p=url.pathname;requests.push(url);
  assert.equal(request.method(),'GET','Visual test must not mutate data');let body;
  if(p.endsWith('/inventory/accounts'))body=[{id:1,account_number:'100-300-100',account_name:'Inv Makanan'}];
  else if(p.endsWith('/warehouses'))body=[{id:5,code:'WH-005',name:'Rumin',is_active:true,location_id:6}];
  else if(p.endsWith('/inventory')){
   let filtered=rows;const search=(url.searchParams.get('search')||'').toLowerCase();if(search)filtered=filtered.filter(r=>(r.product_code+' '+r.product_name+' '+r.warehouse_name).toLowerCase().includes(search));if(url.searchParams.get('health')==='LOW_STOCK')filtered=filtered.filter(r=>r.low_stock);
   const size=Number(url.searchParams.get('page_size')||50),n=Number(url.searchParams.get('page')||1),value=url.searchParams.get('as_of')==='2025-12-31'?0:filtered.reduce((sum,row)=>sum+row.stock_value,0);
   body={items:filtered.slice((n-1)*size,n*size),page:n,page_size:size,total_items:filtered.length,total_pages:Math.ceil(filtered.length/size),has_next:n*size<filtered.length,summary:{stock_lines:filtered.length,stock_value:value,low_stock:filtered.filter(r=>r.low_stock).length},totals_by_account:[{account_id:1,account_code:'100-300-100',account_name:'Inv Makanan',stock_value:value}],totals_by_account_location:[{account_id:1,account_code:'100-300-100',account_name:'Inv Makanan',location_id:6,location_name:'Rumin',stock_value:value}]};
  }else return route.fulfill({status:404,body:'Unmocked API request blocked'});
  return route.fulfill({contentType:'application/json',body:JSON.stringify(body)});
 });
 await page.goto(`http://127.0.0.1:${port}/${suffix}.html`);
 await page.getByRole('button',{name:'View BEEF BALL',exact:true}).waitFor();
 const desktop=await page.locator('.stock-table-scroll').boundingBox();assert.ok(desktop.height>630,'Table must dominate desktop workspace');
 const headerY=await page.getByRole('columnheader',{name:'Item code',exact:true}).evaluate(el=>el.getBoundingClientRect().top);
 await page.locator('.stock-table-scroll').evaluate(el=>{el.scrollTop=400});
 assert.ok(Math.abs(headerY-await page.getByRole('columnheader',{name:'Item code',exact:true}).evaluate(el=>el.getBoundingClientRect().top))<1,'Header must stay fixed');
 await page.locator('.stock-table-scroll').evaluate(el=>{el.scrollTop=0});
 await page.getByRole('button',{name:'View BEEF BALL',exact:true}).click();await page.getByRole('dialog').waitFor();assert.match(await page.getByRole('dialog').innerText(),/BEEF BALL/);await page.getByRole('button',{name:'Close',exact:true}).click();
 await page.getByRole('button',{name:'Account totals',exact:true}).click();await page.getByRole('dialog').waitFor();assert.match(await page.getByRole('dialog').innerText(),/Inv Makanan/);await page.getByRole('button',{name:'Close',exact:true}).click();
 await page.getByRole('textbox',{name:'Search item or warehouse'}).fill('CHICKEN');await page.waitForFunction(()=>document.querySelector('.stock-footer')?.textContent.includes('of 8 stock lines'));
 const before=requests.length;await page.getByRole('textbox',{name:'Search item or warehouse'}).fill('CHICKEN ');await pause(800);assert.equal(requests.length,before,'Trailing whitespace must not refetch forever');
 await page.getByRole('button',{name:'Clear search',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.stock-footer')?.textContent.includes('of 80 stock lines'));
 await page.getByRole('button',{name:'Next page',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.stock-footer-range')?.textContent.includes('51'));
 await page.getByRole('button',{name:/^Reorder/}).click();await page.waitForFunction(()=>document.querySelector('.stock-footer')?.textContent.includes('of 19 stock lines'));
 await page.getByRole('button',{name:'All stock',exact:true}).click();await page.waitForFunction(()=>document.querySelector('.stock-footer')?.textContent.includes('of 80 stock lines'));
 assert.equal(await page.locator('.mmh-workspace-tabs [data-active]').count(),2,'Filtering must reuse one Inventory tab');
 await page.getByRole('button',{name:'Filters',exact:true}).click();await page.getByLabel('Warehouse',{exact:true}).selectOption('5');await page.getByLabel('Inventory account',{exact:true}).selectOption('1');
 await page.getByLabel('From date',{exact:true}).fill('2026-01-01');await page.getByLabel('To date',{exact:true}).fill('2026-10-15');await page.waitForFunction(()=>document.querySelector('.stock-summary-values')?.textContent.includes('Opening'));
 assert.ok(requests.some(url=>url.searchParams.get('as_of')==='2025-12-31'),'Opening must use stock before From date');
 await page.goto(`http://127.0.0.1:${port}/${suffix}.html?date_from=2026-10-20&date_to=2026-10-15`);await page.getByRole('alert').waitFor();assert.match(await page.getByRole('alert').innerText(),/valid date range/);await page.getByRole('button',{name:'Filters',exact:true}).click();
 await page.getByRole('button',{name:'Reset filters',exact:true}).click();await page.getByRole('button',{name:'Filters',exact:true}).click();await page.getByRole('button',{name:'View BEEF BALL',exact:true}).waitFor();await page.goto(`http://127.0.0.1:${port}/${suffix}.html`);await page.getByRole('button',{name:'View BEEF BALL',exact:true}).waitFor();
 await page.getByRole('button',{name:'Table settings',exact:true}).click();await page.getByRole('checkbox',{name:'Average cost',exact:true}).uncheck();assert.equal(await page.getByRole('columnheader',{name:'Avg. cost',exact:true}).count(),0);
 await page.getByRole('checkbox',{name:'Extra compact rows',exact:true}).check();await page.getByRole('heading',{name:'Inventory',exact:true}).click();
 await page.reload();await page.getByRole('button',{name:'View BEEF BALL',exact:true}).waitFor();assert.equal(await page.getByRole('columnheader',{name:'Avg. cost',exact:true}).count(),0);assert.ok(await page.locator('.stock-table-dense').count());
 const print=page.getByRole('button',{name:'Print complete inventory report',exact:true});await print.click();await page.getByRole('dialog').waitFor();await page.frameLocator('iframe').getByText('Grand total',{exact:true}).waitFor();assert.match(await page.frameLocator('iframe').locator('body').innerText(),/80/);await page.getByRole('button',{name:'Close',exact:true}).first().click();
 await page.setViewportSize({width:390,height:844});await pause(100);assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false,'Mobile must not overflow the page');
 if(process.env.QA_SCREENSHOT_DIR){await page.screenshot({path:`${process.env.QA_SCREENSHOT_DIR}/inventory-mobile.png`});await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:`${process.env.QA_SCREENSHOT_DIR}/inventory-desktop.png`});}
 await page.emulateMedia({media:'print'});assert.equal(await page.locator('.stock-table-scroll').evaluate(el=>getComputedStyle(el).overflow),'visible','Print must not clip the table to its screen viewport');await page.emulateMedia({media:'screen'});
 assert.deepEqual(errors,[]);
 console.log('PASS: desktop/mobile layout, frozen header, details, totals, search, pagination, date boundaries, one-tab filters, saved columns/density, full print preview and zero writes.');
}finally{await browser?.close();server?.kill();await Promise.all([unlink(html).catch(()=>{}),unlink(entry).catch(()=>{})]);}
