/** Actual Item Master page, synthetic API only. No signed-in production session. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {writeFile,unlink} from 'node:fs/promises';
import {setTimeout,clearTimeout} from 'node:timers';
import {chromium} from 'playwright-core';
const root=process.cwd(),stem=`.qa-item-priority-${process.pid}`,port=5198;
const files=[`${root}/${stem}.html`,`${root}/${stem}.tsx`];
let server,browser,timer;
try {
 await writeFile(files[0],`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/${stem}.tsx"></script></body></html>`);
 await writeFile(files[1],`import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Page from'./src/modules/master/products/pages/ProductPage';import useAuth from'./src/store/auth';import'./src/styles/index.css';useAuth.setState({user:{id:1,username:'qa',roles:[{name:'SYSTEM_ADMINISTRATOR'}]}});const p=new URLSearchParams(location.search);createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><Page catalogType={p.get('catalog')==='HOTEL'?'HOTEL':'CATERING'} itemType={p.get('type')==='SELL'?'SELL':'BUY'}/></MemoryRouter></QueryClientProvider>);`);
 server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:root,stdio:'pipe',env:{...process.env,VITE_API_URL:`http://127.0.0.1:${port}/api/v1`}});
 await Promise.race([new Promise((resolve,reject)=>{server.stdout.on('data',b=>String(b).includes('Local:')&&resolve());server.once('exit',c=>reject(Error(`Vite exited ${c}`)))}),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Vite startup timed out')),20000)})]);clearTimeout(timer);
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 const page=await browser.newPage();const errors=[],requests=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/api/v1/**',route=>{
   const request=route.request(),url=new URL(request.url());requests.push({path:url.pathname,params:Object.fromEntries(url.searchParams),body:request.postDataJSON()});
   let data=[];
   if(url.pathname.endsWith('/products'))data={items:[],page:1,page_size:50,total_items:0,total_pages:0};
   else if(url.pathname.endsWith('/products/departments'))data={available:true,items:[{id:8,name:'House Keeping'}]};
   else if(url.pathname.endsWith('/exports'))data={job_id:'synthetic',status:'PENDING'};
   else if(url.pathname.endsWith('/classification-master'))data=[];
   return route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(data)});
 });
 for(const catalog of ['HOTEL','CATERING'])for(const type of ['BUY','SELL']){
   requests.length=0;await page.goto(`http://127.0.0.1:${port}/${stem}.html?catalog=${catalog}&type=${type}`);
   await page.getByRole('heading',{name:`${catalog==='HOTEL'?'Hotel':'Catering'} ${type==='SELL'?'Sell':'Buy'} Items`}).waitFor();
   await page.getByRole('button',{name:'New Product',exact:true}).waitFor();
   assert.ok(requests.some(r=>r.path.endsWith('/products')&&r.params.catalog_type===catalog&&r.params.item_type===type));
   await page.getByRole('button',{name:'Usage guide',exact:true}).click();
   await page.getByRole('dialog').getByRole('heading',{name:'Usage guide',exact:true}).waitFor();
   await page.keyboard.press('Escape');
   await page.getByRole('button',{name:'New Product',exact:true}).click();
   const dialog=page.getByRole('dialog');await dialog.getByRole('heading',{name:'New Item'}).waitFor();
   assert.equal(await dialog.getByRole('button',{name:'Buy Item',exact:true}).count(),0);
   assert.equal(await dialog.getByRole('button',{name:'Sell Item',exact:true}).count(),0);
   await dialog.getByText('Department',{exact:true}).waitFor();
   assert.ok(requests.some(r=>r.path.endsWith('/products/departments')&&r.params.catalog_type===catalog));
   await page.keyboard.press('Escape');
   const exportRequest=page.waitForRequest(r=>r.url().endsWith('/exports')&&r.method()==='POST');
   await page.getByRole('button',{name:'Download XLS',exact:true}).click();
   await exportRequest;
   assert.ok(requests.some(r=>r.path.endsWith('/exports')&&r.body.params.catalog_type===catalog&&r.body.params.item_type===type));
 }
 assert.deepEqual(errors,[]);
 console.log('PASS: four catalog/type pages, server filters, locked new-item type, department scope, usage guide and export type; synthetic API only.');
} finally {clearTimeout(timer);await browser?.close();server?.kill('SIGTERM');await Promise.all(files.map(f=>unlink(f).catch(()=>{})));}
