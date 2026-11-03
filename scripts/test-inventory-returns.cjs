/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require('node:assert/strict');
const {setTimeout} = require('node:timers');
const root = require('node:path').resolve(__dirname, '..');
const req = require('node:module').createRequire(root + '/package.json');
const React = req('react'), renderer = req('react-test-renderer');
const { QueryClient, QueryClientProvider } = req('@tanstack/react-query');
global.IS_REACT_ACT_ENVIRONMENT = true;
global.__returnRequests = [];
global.__returnDoc = {id:1,number:'RTN-1',goods_receipt_id:2,warehouse_id:3,receipt_number:'GR-2',supplier_name:'Supplier',purpose:'AP_CREDIT',status:'POSTED',reason:'Damaged',return_date:'2026-11-03',total_cost:40,clearing_balance:40,credit_journal_id:null,items:[{id:4,product_id:5,code:'ITEM-5',name:'Item',uom:'PCS',quantity:4,replaced_quantity:0,line_cost:40}],replacement_receipts:[]};
global.__returnApi = {
  async get(path) {
    if(path==='/inventory/returns')return {data:{items:[global.__returnDoc],total_pages:1}};
    if(path==='/inventory/returns/1')return {data:global.__returnDoc};
    if(path==='/inventory/returns/sources/2')return {data:{id:2,warehouse_id:3,number:'GR-2',items:[],invoices:[{id:6,number:'INV-6',status:'POSTED',balance:20,total:100}]}};
    throw Error('Unexpected GET '+path);
  },
  async post(path,data) {global.__returnRequests.push({path,data});global.__returnDoc={...global.__returnDoc,credit_journal_id:9,credit_reference:data.credit_reference,credit_applied:20,supplier_credit:10};return {data:global.__returnDoc};},
};
(async()=>{
 const result=await req('esbuild').build({absWorkingDir:root,entryPoints:['src/modules/warehouse/inventory-returns/InventoryReturnsPage.tsx'],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime','@tanstack/react-query'],plugins:[{name:'fixtures',setup(b){
   b.onResolve({filter:/^(@\/|react-router-dom$)/},a=>({path:a.path,namespace:'fixture'}));
   b.onLoad({filter:/.*/,namespace:'fixture'},a=>({loader:'js',contents:a.path==='@/api/client'?`export default globalThis.__returnApi;`:a.path.includes('useAuthorization')?`export default ()=>({isSuperuser:()=>true,hasPermission:()=>true});`:a.path.includes('chart-of-accounts')?`export const getAllAccountLookup=async()=>[{id:10,account_code:'CLEAR',account_name:'Clearing',account_type:'ASSET'},{id:11,account_code:'CREDIT',account_name:'Supplier credit',account_type:'ASSET'},{id:12,account_code:'EXP',account_name:'Variance',account_type:'EXPENSE'}];`:a.path.includes('dateConstraints')?`export const todayLocal=()=> '2026-11-03';`:a.path==='react-router-dom'?`import React from 'react';export const Link=p=>React.createElement('a',{href:p.to},p.children);export const useSearchParams=()=>{const [p,s]=React.useState(()=>new URLSearchParams('id=1'));return [p,v=>s(new URLSearchParams(v))]};`:`import React from 'react';export default p=>React.createElement(${a.path.endsWith('/Button')?"'button'":"'div'"},{onClick:p.onClick,disabled:p.disabled},p.children);`}));
 }}]});
 const m={exports:{}};new Function('require','module','exports',result.outputFiles[0].text)(req,m,m.exports);
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});let tree;
 await renderer.act(async()=>{tree=renderer.create(React.createElement(QueryClientProvider,{client},React.createElement(m.exports.default)));await new Promise(r=>setTimeout(r,30));});
 await renderer.act(async()=>{await new Promise(r=>setTimeout(r,30));});
 const field=title=>tree.root.findAllByType('label').find(x=>x.children.some(c=>typeof c==='string'&&c.includes(title)));
 const change=async(node,value)=>renderer.act(async()=>node.props.onChange({target:{value}}));
 await change(field('Original supplier invoice').findByType('select'),'6');
 await change(field('Supplier credit reference').findByType('input'),'CN-TEST');
 await change(field('Credit base amount').findByType('input'),'30');
 await change(field('Excess supplier credit asset').findByType('select'),'11');
 await change(field('Explicit variance expense account').findByType('select'),'12');
 const post=tree.root.findAllByType('button').find(b=>b.children.includes('Post Supplier Credit'));
 assert.equal(post.props.disabled,false);
 await renderer.act(async()=>{post.props.onClick();await new Promise(r=>setTimeout(r,30));});
 assert.deepEqual(global.__returnRequests,[{path:'/inventory/returns/1/credit',data:{supplier_invoice_id:6,credit_date:'2026-11-03',credit_reference:'CN-TEST',net_amount:30,tax_amount:0,supplier_credit_account_id:11,variance_account_id:12}}]);
 assert.ok(!tree.root.findAllByType('button').some(b=>b.children.includes('Post Supplier Credit')),'A settled credit cannot be submitted again');
 await renderer.act(async()=>tree.unmount());client.clear();
 console.log('PASS inventory return UI: original invoice, explicit credit/tax/variance payload, settlement state and duplicate-submit prevention.');
})().catch(error=>{console.error(error);process.exit(1);});
