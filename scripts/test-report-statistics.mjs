import assert from 'node:assert/strict';
import {setTimeout,clearTimeout} from 'node:timers';
import {spawn} from 'node:child_process';
import {writeFile,unlink,mkdir} from 'node:fs/promises';
import {chromium} from 'playwright-core';
const root=process.cwd(),stem=`.qa-report-statistics-${process.pid}`,port=5196;
const files=[`${root}/${stem}.html`,`${root}/${stem}.tsx`];
const names=['Room Available','Room Occupied','Bookkeeping Rate','Number of Guest','Food Cover','Beverage Cover'];
const codes=['900-100-100','900-100-101','900-100-102','900-100-103','900-200-100','900-200-101'];
const keys=['ROOM_AVAILABLE','ROOM_OCCUPIED','BOOKKEEPING_RATE','GUESTS','FOOD_COVERS','BEVERAGE_COVERS'];
const accounts=names.map((name,i)=>({id:i+1,code:codes[i],name,type:'STATISTIC',parent_id:900,normal_balance:'DEBIT',is_posting:false}));
accounts.push({id:10,code:'400-100-100',name:'Room Sales',type:'REVENUE',normal_balance:'CREDIT',parent_id:null,is_posting:true},{id:11,code:'700-100',name:'Expense',type:'EXPENSE',normal_balance:'DEBIT',parent_id:null,is_posting:true});
const options=Object.fromEntries(keys.map((key,i)=>[key,{label:names[i],default_code:codes[i],kind:key==='BOOKKEEPING_RATE'?'latest':'sum'}]));
options.ROOM_SOLD={label:'Paid Room Nights Sold',default_code:null,kind:'sum'};options.ROOM_REVENUE={label:'Room Revenue for ADR',default_code:'400-100-100',kind:'financial'};
const setup={accounts,settings:[],statistic_accounts:{},effective_statistic_accounts:Object.fromEntries(keys.map((k,i)=>[k,i+1])),statistic_options:options};
const amount=(current)=>({current,budget:null,last_month:null,last_year:null,variance:null});
const statistics={available:true,rows:[
 {key:'ROOM_AVAILABLE',label:'Room Available',format:'number',unit:'ROOM_NIGHT',periods:{MTD:amount(100),YTD:amount(200)}},
 {key:'OCCUPANCY',label:'Occupancy',format:'percent',unit:'%',periods:{MTD:amount(.2),YTD:amount(.5)}},
 {key:'ADR',label:'Average Room Rate / ADR',format:'money',unit:'IDR',periods:{MTD:amount(null),YTD:amount(null)}},
 {key:'BOOKKEEPING_RATE',label:'Bookkeeping Rate',format:'number',unit:'IDR/USD',periods:{MTD:amount(16500),YTD:amount(16500)}},
]};
const report={statistics,scope:{business_unit_id:1,location_id:8,department_id:null},scope_labels:{business_unit_id:'Hotel',location_id:'Hotel'},presentation_rows:[],rows:[],periods:{MTD:{},YTD:{}},section_totals:{}};
let server,browser,timer;
try{
 await writeFile(files[0],`<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"></head><body><div id="root"></div><script type="module" src="/${stem}.tsx"></script></body></html>`);
 await writeFile(files[1],`import{createRoot}from'react-dom/client';import{MemoryRouter}from'react-router-dom';import{QueryClient,QueryClientProvider}from'@tanstack/react-query';import Stats from'./src/modules/finance/financial-statements/ReportStatisticsTable';import Setup from'./src/modules/finance/setup/ReportSetupPage';import Entry from'./src/modules/finance/statistics/StatisticsPage';import{FinancialStatementPrint}from'./src/modules/finance/financial-statements/FinancialReportPrintPage';import useAuth from'./src/store/auth';import'./src/styles/index.css';useAuth.setState({user:{id:1,username:'qa',roles:[{name:'SYSTEM_ADMINISTRATOR'}]}});const mode=new URLSearchParams(location.search).get('mode');createRoot(document.getElementById('root')!).render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter>{mode==='setup'?<Setup/>:mode==='entry'?<Entry/>:mode==='print'?<FinancialStatementPrint kind="PROFIT_LOSS" data={${JSON.stringify(report)} as any} asOf="2026-02-28"/>:<Stats data={${JSON.stringify(statistics)} as any} periods={['MTD','YTD']}/>}</MemoryRouter></QueryClientProvider>);`);
 server=spawn(process.execPath,['node_modules/vite/bin/vite.js','--host','127.0.0.1','--port',String(port),'--strictPort'],{cwd:root,stdio:'pipe'});
 await Promise.race([new Promise((resolve,reject)=>{server.stdout.on('data',b=>String(b).includes('Local:')&&resolve());server.once('exit',c=>reject(Error(`Vite exited ${c}`)))}),new Promise((_,reject)=>{timer=setTimeout(()=>reject(Error('Vite timeout')),20000);})]);clearTimeout(timer);
 browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM_PATH||undefined,args:['--no-sandbox','--disable-dev-shm-usage','--disable-gpu']});
 const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[],writes=[],unknown=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.route('**/*',route=>{
  const req=route.request();if(!['xhr','fetch'].includes(req.resourceType()))return route.continue();const p=new URL(req.url()).pathname;let data;
  if(req.method()!=='GET'){writes.push({path:p,data:req.postDataJSON()});data={message:'Synthetic save'};}
  else if(p.endsWith('/financial-reports/setup'))data=setup;
  else if(p.endsWith('/chart-of-accounts/lookup'))data=accounts.map(a=>({...a,account_code:a.code,account_name:a.name,account_type:a.type,is_active:true})).filter(a=>a.account_type==='STATISTIC');
  else if(p.endsWith('/locations'))data=[{id:8,name:'Hotel',code:'HOTEL',business_unit_id:1,is_active:true}];
  else if(p.endsWith('/departments'))data=[{id:7,name:'Food and Beverage',business_unit_id:1,is_active:true}];
  else if(p.endsWith('/statistics'))data={items:[],total_items:0,total_pages:1};
  else{unknown.push(p);return route.fulfill({status:404,body:'Unmocked API blocked'});}
  return route.fulfill({contentType:'application/json',body:JSON.stringify(data)});
 });
 const go=mode=>page.goto(`http://127.0.0.1:${port}/${stem}.html?mode=${mode}`);
 await go('report');await page.getByText('Operating Statistics',{exact:true}).waitFor();
 assert.match(await page.locator('tbody tr').filter({hasText:'Occupancy'}).innerText(),/20%.*50%/s);
 assert.match(await page.locator('tbody tr').filter({hasText:'Bookkeeping Rate'}).innerText(),/IDR\/USD/);
 assert.match(await page.locator('tbody tr').filter({hasText:'Average Room Rate'}).innerText(),/—/);
 await go('print');await page.locator('[data-print-ready="true"]').waitFor();assert.equal(await page.getByRole('heading',{name:'Operating Statistics'}).count(),1);
 await go('setup');await page.getByText('Statistics and ADR sources',{exact:true}).click();
 await page.getByLabel('Paid Room Nights Sold source').selectOption('2');
 assert.equal(await page.getByLabel('Bookkeeping Rate source').locator('option[value="10"]').count(),0,'Financial revenue cannot be a statistical rate');
 assert.equal(await page.getByLabel('Room Revenue for ADR source').locator('option[value="11"]').count(),0,'Expense cannot be Room Revenue');
 if(process.env.QA_SCREENSHOT_DIR){await mkdir(process.env.QA_SCREENSHOT_DIR,{recursive:true});await page.screenshot({path:`${process.env.QA_SCREENSHOT_DIR}/report-statistics-setup.png`});}
 await Promise.all([page.waitForResponse(r=>r.request().method()==='PUT'),page.getByRole('button',{name:'Save',exact:true}).click()]);
 assert.equal(writes[0].data.statistic_accounts.ROOM_SOLD,2);
 await go('entry');await page.getByRole('button',{name:'Add Statistic'}).click();const dialog=page.getByRole('dialog');
 await dialog.getByLabel('Metric',{exact:true}).selectOption('1');
 assert.equal(await dialog.getByLabel('Unit',{exact:true}).inputValue(),'ROOM_NIGHT');
 await dialog.getByLabel('Location',{exact:true}).selectOption('8');await dialog.getByLabel('Month',{exact:true}).fill('2026-01');await dialog.getByLabel('Actual',{exact:true}).fill('0');await dialog.getByLabel('Budget',{exact:true}).fill('3100');
 assert.match(await dialog.innerText(),/3,100 room-nights/);
 await dialog.getByRole('button',{name:'Save',exact:true}).click();await dialog.waitFor({state:'hidden'});
 assert.equal(writes[1].data.actual,'0');assert.equal(writes[1].data.unit,'ROOM_NIGHT');assert.equal(writes[1].data.period,'2026-01-01');
 await page.getByRole('button',{name:'Add Statistic'}).click();await dialog.getByLabel('Metric',{exact:true}).selectOption('3');
 assert.equal(await dialog.getByLabel('Unit',{exact:true}).inputValue(),'');await dialog.getByLabel('Unit',{exact:true}).fill('IDR/USD');
 assert.match(await dialog.innerText(),/period-end bookkeeping exchange rate/);
 if(process.env.QA_SCREENSHOT_DIR)await page.screenshot({path:`${process.env.QA_SCREENSHOT_DIR}/report-statistics-rate-entry.png`});
 assert.deepEqual(errors,[]);assert.deepEqual(unknown,[]);
 console.log('PASS: statistics/print percentages, ADR unavailable without paid-room source, mapping selectors/payload, monthly room-night unit help, zero input, currency-pair entry; synthetic API only.');
}finally{clearTimeout(timer);await browser?.close();server?.kill();await Promise.all(files.map(f=>unlink(f).catch(()=>{})));}
