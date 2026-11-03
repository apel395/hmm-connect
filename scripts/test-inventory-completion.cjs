/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict');
const {setTimeout}=require('node:timers');
const root=require('node:path').resolve(__dirname,'..');
const req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');
const {QueryClient,QueryClientProvider}=req('@tanstack/react-query');
global.IS_REACT_ACT_ENVIRONMENT=true;
global.__completionApi={async get(path){assert.equal(path,'/inventory/returns/1/credit-invoices');return {data:{items:[{id:7,number:'INV-7',balance:80}],total_pages:1}};}};
(async()=>{
 const result=await req('esbuild').build({absWorkingDir:root,entryPoints:['src/modules/warehouse/inventory-returns/ReturnCompletion.tsx'],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime','@tanstack/react-query'],plugins:[{name:'fixtures',setup(b){
 b.onResolve({filter:/^(@\/|react-router-dom$)/},a=>({path:a.path,namespace:'fixture'}));
 b.onLoad({filter:/.*/,namespace:'fixture'},a=>({loader:'js',contents:a.path==='@/api/client'?`export default globalThis.__completionApi;`:a.path.includes('dateConstraints')?`export const todayLocal=()=> '2026-11-03';`:a.path==='react-router-dom'?`import React from 'react';export const Link=p=>React.createElement('a',{href:p.to},p.children);`:`import React from 'react';export default p=>React.createElement('button',{onClick:p.onClick,disabled:p.disabled},p.children);`}));
 }}]});
 const m={exports:{}};new Function('require','module','exports',result.outputFiles[0].text)(req,m,m.exports);
 const requests=[];const props={id:1,status:'POSTED',balance:30,history:[],canManage:true,pending:false,
 accounts:[{id:8,account_code:'BANK',account_name:'Bank',account_type:'ASSET',account_subtype:'BANK'},
 {id:9,account_code:'INV',account_name:'Inventory',account_type:'ASSET',account_subtype:'INVENTORY'}],submit:v=>requests.push(v)};
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});let tree;
 const mount=async(value)=>{await renderer.act(async()=>{tree=renderer.create(React.createElement(QueryClientProvider,{client},React.createElement(m.exports.default,value)));await new Promise(r=>setTimeout(r,30));});await renderer.act(async()=>{await new Promise(r=>setTimeout(r,30));});};
 const field=title=>tree.root.findAllByType('label').find(x=>x.children.some(c=>typeof c==='string'&&c===title));
 const change=async(title,type,value)=>renderer.act(async()=>field(title).findByType(type).props.onChange({target:{value}}));
 const button=title=>tree.root.findAllByType('button').find(b=>b.children.join('')===title);
 await mount(props);
 await change('Target invoice','select','7');await change('Amount','input','20');await change('Reference','input','USE-1');await change('Reason','input','Apply credit');
 assert.equal(button('Post Credit Application').props.disabled,false);
 await renderer.act(async()=>button('Post Credit Application').props.onClick());
 assert.equal(requests[0].path,'/inventory/returns/1/credit-use');assert.equal(requests[0].data.supplier_invoice_id,7);assert.equal(requests[0].data.cash_account_id,null);assert.equal(requests[0].data.amount,20);assert.ok(requests[0].data.request_key);
 await change('Action','select','REFUND');await change('Refund cash / bank account','select','8');
 assert.equal(field('Refund cash / bank account').findAllByType('option').length,2,'Only cash/bank accounts appear');
 await renderer.act(async()=>button('Post Supplier Refund').props.onClick());assert.equal(requests[1].data.cash_account_id,8);assert.equal(requests[1].data.supplier_invoice_id,null);
 await renderer.act(async()=>tree.unmount());
 await mount({...props,balance:10,history:[{id:5,kind:'APPLY',date:'2026-11-03',amount:20,reference:'USE-1',reason:'Credit',journal_entry_id:99,reversed:false}]});
 assert.equal(field('Reverse').findAllByType('option').find(o=>o.props.value==='RETURN').props.disabled,true);
 await change('Reverse','select','5');await change('Correction reference','input','FIX-1');await change('Correction reason','input','Wrong invoice');
 assert.equal(button('Post Reversal').props.disabled,false);await renderer.act(async()=>button('Post Reversal').props.onClick());
 assert.equal(requests[2].path,'/inventory/returns/1/events/5/reverse');assert.equal(requests[2].data.reason,'Wrong invoice');
 await renderer.act(async()=>tree.unmount());
 await mount({...props,canManage:false});assert.equal(tree.root.findAllByType('button').length,0,'Non-finance users cannot settle or reverse');
 await renderer.act(async()=>tree.unmount());client.clear();
 console.log('PASS supplier-credit UI: invoice use, bank refund, correction payload, dependency controls and permissions.');
})().catch(error=>{console.error(error);process.exit(1);});
