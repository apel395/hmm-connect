/* global require, __dirname, global, EventTarget, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict'),root=require('node:path').resolve(__dirname,'..'),req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');global.IS_REACT_ACT_ENVIRONMENT=true;
const values=new Map();global.window=Object.assign(new EventTarget(),{localStorage:{getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}});
const payloads=[];let fail=true;
global.__receiptApi={post:async(path,payload)=>{assert.equal(path,'/customer-payments');payloads.push(payload);if(fail)throw new Error('Connection interrupted');return {data:{id:1}};}};
async function run(){
 const bundle=await req('esbuild').build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/finance/accounts-receivable/ARReceiptForm.tsx'],bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime'],plugins:[{name:'mocks',setup(b){
 b.onResolve({filter:/^(?:@\/components\/|@\/store\/auth|@\/api\/client|sonner|@tanstack\/react-query)/},a=>({path:a.path,namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},a=>{let contents;
 if(a.path==='@/api/client')contents='export default globalThis.__receiptApi;';
 else if(a.path==='@/store/auth')contents='export default s=>s({user:{id:45}});';
 else if(a.path==='sonner')contents='export const toast={success(){}};';
 else if(a.path==='@tanstack/react-query')contents='export const useQueryClient=()=>({invalidateQueries:async()=>{}});export const useQuery=()=>({data:{cash_accounts:[{id:115,name:"Bank"}]}});export const useMutation=o=>({isPending:false,mutate:async()=>{try{const r=await o.mutationFn();o.onSuccess?.(r);}catch(e){o.onError?.(e);}}});';
 else if(a.path.includes('SearchableSelect'))contents=`import React from 'react';export default p=>React.createElement('select',{'aria-label':p.label,value:p.value??'',onChange:e=>p.onChange(Number(e.target.value))},p.options.map(o=>React.createElement('option',{key:o.id,value:o.id},o.name)));`;
 else if(a.path.endsWith('/Dialog'))contents=`import React from 'react';const Part=({children})=>React.createElement('div',null,children);export const DialogBody=Part,DialogContent=Part,DialogFooter=Part,DialogHeader=Part,DialogTitle=Part;export default ({open,children})=>open?React.createElement('div',null,children):null;`;
 else contents=`import React from 'react';export default p=>React.createElement('button',{onClick:p.onClick,disabled:p.disabled},p.children);`;
 return {contents,loader:'js'};});}}]});
 const m={exports:{}};new Function('module','exports','require',bundle.outputFiles[0].text)(m,m.exports,n=>req(n));const Form=m.exports.default;
 const text=n=>n.children.map(c=>typeof c==='string'?c:text(c)).join('');
 const click=async(v,label)=>{await renderer.act(async()=>{await v.root.findAllByType('button').find(b=>text(b)===label).props.onClick();});};
 const mount=async()=>{let v;await renderer.act(async()=>{v=renderer.create(React.createElement(Form,{invoiceId:12,outstanding:'100000'}));});return v;};
 let v=await mount();await click(v,'Receive Payment');
 await renderer.act(async()=>{v.root.findByProps({'aria-label':'Amount received'}).props.onChange({target:{value:'40000'}});v.root.findByProps({'aria-label':'Receipt date'}).props.onChange({target:{value:'2026-10-22'}});v.root.findByProps({'aria-label':'Cash / bank account'}).props.onChange({target:{value:'115'}});v.root.findByProps({'aria-label':'Receipt reference'}).props.onChange({target:{value:'BCA-1'}});});
 await click(v,'Post Receipt');assert.equal(payloads[0].amount,'40000');assert.equal(payloads[0].account_receivable_id,12);assert.equal(payloads[0].cash_account_id,115);
 await click(v,'Close');await renderer.act(async()=>v.unmount());v=await mount();await click(v,'Receive Payment');
 assert.equal(v.root.findByProps({'aria-label':'Amount received'}).props.value,'40000');assert.equal(v.root.findByProps({'aria-label':'Receipt reference'}).props.value,'BCA-1');
 fail=false;await click(v,'Post Receipt');assert.equal(payloads.length,2);assert.equal(payloads[0].idempotency_key,payloads[1].idempotency_key,'retry reuses receipt key after close and refresh');
 await renderer.act(async()=>v.unmount());v=await mount();await click(v,'Receive Payment');assert.equal(v.root.findByProps({'aria-label':'Amount received'}).props.value,'100000','successful receipt clears recovered input');await renderer.act(async()=>v.unmount());
 console.log('AR receipt PASS: partial amount, explicit bank, retained input and stable retry key after refresh.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
