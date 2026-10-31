/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict'),root=require('node:path').resolve(__dirname,'..'),req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');global.IS_REACT_ACT_ENVIRONMENT=true;global.__saved=[];global.__errors=[];
const receipt={id:10,receipt_number:'GR-EDIT',status:'DRAFT',source_type:'HISTORICAL_ENTRY',received_at:'2026-01-03T10:00:00Z',supplier_name:'Supplier',business_unit_id:1,department_id:1,location_id:1,destination_type:'DIRECT_USE',items:[1,2].map(id=>({id,product_id:100+id,product_name:`Item ${id}`,product_code:`CODE-${id}`,catalog_type:'CATERING',inventory_treatment:'DIRECT_USE',destination_type:'DIRECT_USE',quantity:2,unit_cost:10,is_taxable:false,tax_rate:0,master_is_taxable:true,master_tax_rate:11}))};
async function run(){
 const bundled=await req('esbuild').build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/purchasing/goods-receipts/components/EditReceivingDialog.tsx'],loader:{'.css':'empty'},bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime'],plugins:[{name:'mocks',setup(b){
 b.onResolve({filter:/^(?:@\/api\/client|@\/components\/|@\/modules\/|@tanstack\/react-query|sonner|lucide-react|\.\.\/hooks\/useGoodsReceipts|\.\/ReceivingDestinationField)/},a=>({path:a.path,namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},a=>{let contents;
 if(a.path==='@/api/client')contents='export default {get:async()=>({data:{discount_account:null}})};';
 else if(a.path==='sonner')contents='export const toast={error:x=>globalThis.__errors.push(x),success:()=>{}};';
 else if(a.path==='lucide-react')contents='export const Trash2=()=>null;';
 else if(a.path.includes('useGoodsReceipts'))contents='export const useUpdateGoodsReceipt=()=>({isPending:false,mutateAsync:async x=>globalThis.__saved.push(x)});';
 else if(a.path.includes('useWarehouses'))contents='export const useWarehouses=()=>({data:[]});';
 else if(a.path.includes('chart-of-accounts'))contents='export const getAllAccountLookup=async()=>[];';
 else if(a.path.includes('/organization/'))contents='export const listLocations=async()=>[];';
 else if(a.path==='@tanstack/react-query')contents='export const useQuery=()=>({data:[]});';
 else if(a.path.includes('ProductCombobox'))contents="import React from 'react';export default p=>React.createElement('product-picker',p);";
 else if(a.path.endsWith('/Dialog'))contents="import React from 'react';export const DialogBody=p=>React.createElement('div',null,p.children);export const DialogContent=DialogBody,DialogFooter=DialogBody,DialogHeader=DialogBody,DialogTitle=DialogBody;export default p=>p.open?React.createElement('div',null,p.children):null;";
 else if(a.path.includes('/Button'))contents="import React from 'react';export default p=>React.createElement('button',p,p.children);";
 else contents="import React from 'react';export default p=>React.createElement('div',null,p.children);";
 return {contents,loader:'js'};});}}]});
 const m={exports:{}};new Function('module','exports','require',bundled.outputFiles[0].text)(m,m.exports,n=>req(n));const Page=m.exports.default;
 let v;const mount=async()=>{await renderer.act(async()=>{v=renderer.create(React.createElement(Page,{open:true,receipt,onClose(){}}));});};const text=n=>n.children.map(c=>typeof c==='string'?c:text(c)).join('');const save=()=>v.root.findAllByType('button').find(n=>text(n)==='Save Changes');
 await mount();const removes=v.root.findAllByType('button').filter(n=>String(n.props['aria-label']).startsWith('Remove item '));assert.equal(removes.length,2,'saved lines have remove action');await renderer.act(async()=>removes[0].props.onClick());assert.ok(v.root.findAllByType('button').find(n=>String(n.props['aria-label']).startsWith('Remove item ')).props.disabled,'keep at least one line');await renderer.act(async()=>save().props.onClick());assert.equal(global.__saved[0].payload.items.length,1);assert.equal(global.__saved[0].payload.items[0].item_id,2);assert.equal(global.__saved[0].payload.items[0].tax_rate,11);assert.equal(global.__saved[0].payload.items[0].is_taxable,true);assert.equal(v.root.findAllByType('input').filter(n=>String(n.props['aria-label']).includes('PPN')).length,0,'PPN has no editable percentage input');await renderer.act(async()=>v.unmount());
 await mount();const picker=v.root.findAllByType('product-picker')[0];assert.equal(picker.props.value,101);await renderer.act(async()=>picker.props.onSelect({id:303,name:'Replacement',code:'NEW-303',catalog_type:'CATERING',uom:'Box',inventory_treatment:'DIRECT_USE',reference_cost:15,is_taxable:false}));await renderer.act(async()=>save().props.onClick());const lines=global.__saved[1].payload.items;assert.equal(lines[0].product_id,303);assert.ok(!('item_id' in lines[0]),'replacement gets a new line identity');assert.equal(lines[1].item_id,2);assert.equal(lines[0].unit_cost,15);assert.equal(global.__errors.length,0);await renderer.act(async()=>v.unmount());
 console.log('Receiving edit PASS: saved-line removal, last-line protection, item reselection with new identity and retained untouched rows.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
