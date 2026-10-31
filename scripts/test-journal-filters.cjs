/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict');
const {URL}=require('node:url');
const root=require('node:path').resolve(__dirname,'..');
const req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');
const {QueryClient,QueryClientProvider}=req('@tanstack/react-query');
const {MemoryRouter}=req('react-router-dom');
global.IS_REACT_ACT_ENVIRONMENT=true;
global.window={localStorage:{getItem:()=>null,setItem:()=>{}}};
global.__journalRequests=[];
async function run(){
 const helpers=await req('esbuild').build({absWorkingDir:root,entryPoints:['src/modules/finance/journals/journalFilters.ts'],bundle:true,write:false,platform:'node',format:'cjs'});
 const hm={exports:{}};new Function('module','exports',helpers.outputFiles[0].text)(hm,hm.exports);
 const path=hm.exports.unbalancedJournalPath({date_from:'2026-01-01',date_to:'2026-01-31',business_unit_id:1,location_id:8,department_id:3,supplier_id:4,reference_type:'MANUAL',account_id:55,search:'partial line'});
 const params=new URL('https://example.test'+path).searchParams;
 assert.equal(params.get('balance_state'),'UNBALANCED');assert.equal(params.get('status'),'POSTED');
 for(const key of ['date_from','date_to','business_unit_id','location_id','department_id','supplier_id','reference_type'])assert.ok(params.get(key));
 assert.equal(new URL('https://example.test'+hm.exports.unbalancedJournalPath({})).searchParams.get('business_unit_id'),'all');
 assert.equal(params.get('account_id'),null,'GL shortcut inspects whole journals');
 assert.equal(params.get('difference_amount'),null,'Multiple differences may net to the GL difference');
 assert.deepEqual(hm.exports.journalFilterParams({difference_amount:0,account_id:undefined,search:''}),{difference_amount:0});
 const bundle=await req('esbuild').build({absWorkingDir:root,entryPoints:['src/modules/finance/journals/JournalListPage.tsx'],jsx:'automatic',bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime','react-router-dom','@tanstack/react-query'],plugins:[{name:'fixtures',setup(b){
 b.onResolve({filter:/^\.\/api$/},a=>a.importer.endsWith('JournalListPage.tsx')?{path:a.path,namespace:'mock'}:undefined);
 b.onResolve({filter:/^(@\/|sonner$|lucide-react$|\.\/JournalBulkImportDialog$)/},a=>({path:a.path,namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},a=>{
 let contents;
 if(a.path==='./api')contents=`export const getJournalScope=async()=>({units:[{id:1,name:'Hotel'}],locations:[{id:8,name:'Hotel',business_unit_id:1}],default_business_unit_id:null,default_location_id:null,location_locked:false});export const listJournals=async p=>{globalThis.__journalRequests.push(p);return {items:[{id:1,journal_number:'DIFF-45000',journal_date:'2026-01-02',reference_type:'MANUAL',total_debit:1,total_credit:45001,difference:-45000,status:'POSTED',allowed_actions:{}}],summary:{total_debit:1,total_credit:45001},reference_types:['MANUAL'],total_items:1,total_pages:1}};export const bulkJournalAction=async()=>{},createJournal=async()=>{},journalAction=async()=>{},getJournalCopyTemplate=async()=>{};`;
 else if(a.path.includes('organization/api'))contents="export const filterBusinessUnits=async()=>[],listDepartments=async()=>[{id:3,name:'Accounting'}],listLocations=async()=>[];";
 else if(a.path.includes('chart-of-accounts'))contents="export const getAllAccountLookup=async()=>[{id:55,account_code:'100',account_name:'Cash'}];";
 else if(a.path.includes('suppliers/api'))contents="export const supplierApi={lookup:async()=>[]};";
 else if(a.path.includes('payments/api'))contents="export const paymentAction=async()=>{};";
 else if(a.path.includes('useAuthorization'))contents="export default ()=>({isSuperuser:()=>false});";
 else if(a.path.includes('useFormRecovery'))contents="export default ()=>({load:()=>null,clear:()=>{},notifyRestored:()=>{}});";
 else if(a.path.includes('dateConstraints'))contents="export const todayLocal=()=> '2026-01-01';";
 else if(a.path==='sonner')contents="export const toast={success:()=>{},error:()=>{}};";
 else if(a.path==='lucide-react')contents="export const SlidersHorizontal=()=>null;";
 else if(a.path.includes('SearchableSelect'))contents="import React from 'react';export default p=>React.createElement('picker',p);";
 else if(a.path.includes('PageHeader'))contents="import React from 'react';export default p=>React.createElement('header',null,p.actions,p.children);";
 else if(a.path.includes('PrintPreviewButton'))contents="import React from 'react';export default p=>React.createElement('print-preview',p);";
 else if(a.path.includes('/Table'))contents="import React from 'react';const C=p=>React.createElement('cell',p,p.children);export const Table=C,TBody=C,TD=C,TH=C,THead=C,TR=C,TableCellStack=C;";
 else if(a.path.includes('/Dialog'))contents="import React from 'react';const C=p=>React.createElement('div',null,p.children);export const DialogBody=C,DialogContent=C,DialogFooter=C,DialogHeader=C,DialogTitle=C;export default p=>p.open?React.createElement(C,p):null;";
 else if(a.path.includes('/Button'))contents="import React from 'react';export default p=>React.createElement('button',p,p.children);";
 else if(a.path==='./JournalBulkImportDialog')contents="export default ()=>null;";
 else contents="import React from 'react';export default p=>React.createElement('div',p,p.children);";
 return {contents,loader:'js'};
 });}}]});
 const m={exports:{}};new Function('module','exports','require',bundle.outputFiles[0].text)(m,m.exports,n=>req(n));
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});let view;
 await renderer.act(async()=>{view=renderer.create(React.createElement(QueryClientProvider,{client},React.createElement(MemoryRouter,{initialEntries:[path]},React.createElement(m.exports.default))));});
 await renderer.act(async()=>{await new Promise(resolve=>global.setTimeout(resolve,30));});
 const last=()=>global.__journalRequests.at(-1);
 assert.equal(last().location_id,8);assert.equal(last().business_unit_id,1);assert.equal(last().status,'POSTED');assert.equal(last().balance_state,'UNBALANCED');assert.equal(last().date_from,'2026-01-01');
 const input=view.root.findAllByType('input').find(n=>n.props['aria-label']==='Difference amount');
 await renderer.act(async()=>input.props.onChange({target:{value:'45000'}}));
 await renderer.act(async()=>{await new Promise(resolve=>global.setTimeout(resolve,15));});
 assert.equal(last().difference_amount,'45000');assert.equal(last().page,1);
 const picker=view.root.findAllByType('picker').find(n=>n.props.label==='Account');await renderer.act(async()=>picker.props.onChange(55));
 await renderer.act(async()=>{await new Promise(resolve=>global.setTimeout(resolve,15));});assert.equal(last().account_id,55);
 assert.ok(view.root.findAllByType('cell').some(n=>n.children.includes('Difference')));
 assert.ok(view.root.findAllByType('cell').some(n=>String(n.props.className).includes('text-red-700')));
 assert.ok(view.root.findByType('print-preview').props.src.includes('difference_amount=45000'));
 await renderer.act(async()=>view.unmount());client.clear();
 console.log('Journal filters PASS: GL scope link, both-sign difference query, account filter, page reset, difference column and print parameters.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
