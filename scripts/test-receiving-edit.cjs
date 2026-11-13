/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict'),root=require('node:path').resolve(__dirname,'..'),req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');global.IS_REACT_ACT_ENVIRONMENT=true;global.__saved=[];global.__errors=[];
const receipt={id:10,receipt_number:'GR-EDIT',status:'DRAFT',source_type:'HISTORICAL_ENTRY',received_at:'2026-01-03T10:00:00Z',supplier_name:'Supplier',business_unit_id:1,department_id:1,location_id:1,destination_type:'DIRECT_USE',items:[1,2].map(id=>({id,product_id:100+id,product_name:`Item ${id}`,product_code:`CODE-${id}`,catalog_type:'CATERING',inventory_treatment:'DIRECT_USE',destination_type:'DIRECT_USE',quantity:2,unit_cost:10,is_taxable:true,tax_rate:5,master_is_taxable:true,master_tax_rate:11}))};
async function run(){
 const bundled=await req('esbuild').build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/purchasing/goods-receipts/components/EditReceivingDialog.tsx'],loader:{'.css':'empty'},bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime'],plugins:[{name:'mocks',setup(b){
 b.onResolve({filter:/^(?:@\/api\/client|@\/components\/|@\/modules\/|@tanstack\/react-query|sonner|lucide-react|\.\.\/hooks\/useGoodsReceipts|\.\/ReceivingDestinationField)/},a=>({path:a.path,namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},a=>{let contents;
 if(a.path==='@/api/client')contents='export default {get:async()=>({data:{discount_account:null}})};';
 else if(a.path==='sonner')contents='export const toast={error:x=>globalThis.__errors.push(x),success:()=>{}};';
 else if(a.path==='lucide-react')contents='export const Trash2=()=>null;';
 else if(a.path.includes('useGoodsReceipts'))contents='export const useUpdateGoodsReceipt=()=>({isPending:false,mutateAsync:async x=>globalThis.__saved.push(x)});export const useCorrectHistoricalReceipt=()=>({isPending:false,mutateAsync:async x=>globalThis.__saved.push(x)});';
 else if(a.path.includes('useWarehouses'))contents='export const useWarehouses=()=>({data:globalThis.__warehouseList??[]});';
 else if(a.path.includes('chart-of-accounts'))contents='export const getAllAccountLookup=async()=>[];';
 else if(a.path.includes('/organization/'))contents='export const listLocations=async()=>[];export const listDepartments=async()=>[];export const filterBusinessUnits=async()=>[];';
 else if(a.path.includes('useSuppliers'))contents='export const useSuppliers=()=>({data:[]});';
 else if(a.path==='@tanstack/react-query')contents='export const useQuery=()=>({data:[]});';
 else if(a.path.includes('ProductCombobox'))contents="import React from 'react';export default p=>React.createElement('product-picker',p);";
 else if(a.path.endsWith('SearchableSelect'))contents="import React from 'react';export default p=>React.createElement('select',{'aria-label':p.label,value:p.value??'',options:p.options,onChange:e=>p.onChange(Number(e.target.value)||undefined)},(p.options??[]).map(row=>React.createElement('option',{key:row.id,value:row.id},row.label)));";
 else if(a.path.endsWith('/Dialog'))contents="import React from 'react';export const DialogBody=p=>React.createElement('div',null,p.children);export const DialogContent=DialogBody,DialogFooter=DialogBody,DialogHeader=DialogBody,DialogTitle=DialogBody;export default p=>p.open?React.createElement('div',null,p.children):null;";
 else if(a.path.includes('/Button'))contents="import React from 'react';export default p=>React.createElement('button',p,p.children);";
 else contents="import React from 'react';export default p=>React.createElement('div',null,p.children);";
 return {contents,loader:'js'};});}}]});
 const m={exports:{}};new Function('module','exports','require',bundled.outputFiles[0].text)(m,m.exports,n=>req(n));const Page=m.exports.default;
 let v;const mount=async()=>{await renderer.act(async()=>{v=renderer.create(React.createElement(Page,{open:true,receipt,onClose(){}}));});};const text=n=>n.children.map(c=>typeof c==='string'?c:text(c)).join('');const save=()=>v.root.findAllByType('button').find(n=>text(n)==='Save Changes');
 await mount();const removes=v.root.findAllByType('button').filter(n=>String(n.props['aria-label']).startsWith('Remove item '));assert.equal(removes.length,2,'saved lines have remove action');await renderer.act(async()=>removes[0].props.onClick());assert.ok(v.root.findAllByType('button').find(n=>String(n.props['aria-label']).startsWith('Remove item ')).props.disabled,'keep at least one line');const taxInput=v.root.findAllByType('input').find(n=>String(n.props['aria-label']).startsWith('PPN rate'));assert.equal(taxInput.props.value,5,'edit loads recorded tax, not master rate');await renderer.act(async()=>taxInput.props.onChange({target:{value:'7.5'}}));await renderer.act(async()=>save().props.onClick());assert.equal(global.__saved[0].payload.items.length,1);assert.equal(global.__saved[0].payload.items[0].item_id,2);assert.equal(global.__saved[0].payload.items[0].tax_rate,7.5);assert.equal(global.__saved[0].payload.items[0].is_taxable,true);assert.equal(v.root.findAllByType('input').filter(n=>String(n.props['aria-label']).includes('PPN')).length,1,'PPN percentage is editable');await renderer.act(async()=>v.unmount());
 await mount();const picker=v.root.findAllByType('product-picker')[0];assert.equal(picker.props.value,101);await renderer.act(async()=>picker.props.onSelect({id:303,name:'Replacement',code:'NEW-303',catalog_type:'CATERING',uom:'Box',inventory_treatment:'DIRECT_USE',reference_cost:15,is_taxable:false}));await renderer.act(async()=>save().props.onClick());const lines=global.__saved[1].payload.items;assert.equal(lines[0].product_id,303);assert.ok(!('item_id' in lines[0]),'replacement gets a new line identity');assert.equal(lines[1].item_id,2);assert.equal(lines[0].unit_cost,15);assert.equal(global.__errors.length,0);await renderer.act(async()=>v.unmount());
 receipt.status='POSTED';receipt.supplier_id=1;receipt.source_type='HISTORICAL_ENTRY';
 await mount();
 const correctionReason=v.root.findAllByType('textarea').find(n=>n.props.maxLength===500);
 assert.ok(correctionReason,'historical editor requires correction reason');
 await renderer.act(async()=>correctionReason.props.onChange({target:{value:'Fix the historical supplier reference'}}));
 const referenceLabel=v.root.findAllByType('label').find(n=>text(n).includes('Delivery Note / Reference'));
 assert.ok(referenceLabel,'full historical editor exposes delivery reference');
 await renderer.act(async()=>referenceLabel.findByType('input').props.onChange({target:{value:'HIST-REF-2026'}}));
 const historicalSave=v.root.findAllByType('button').find(n=>text(n)==='Save Historical Correction');
 assert.ok(historicalSave,'historical editor has a dedicated save action');
 await renderer.act(async()=>historicalSave.props.onClick());
 const historicalPayload=global.__saved.at(-1).payload;
 assert.equal(historicalPayload.external_reference,'HIST-REF-2026');
 assert.equal(historicalPayload.reason,'Fix the historical supplier reference');
 assert.equal(historicalPayload.supplier_id,1);
 assert.ok(!('received_at' in historicalPayload),'unchanged historical timestamp is not rewritten');
 assert.equal(historicalPayload.remove_item_ids.length,0);
 assert.equal(historicalPayload.items.length,2);
 await renderer.act(async()=>v.unmount());
 // Historical location correction must not silently replace the original physical warehouse.
 global.__warehouseList=[
   {id:91,code:'WH-OLD',name:'Original stock',location_id:1,is_active:true},
   {id:92,code:'WH-NEW',name:'Corrected location',location_id:2,is_active:true},
 ];
 receipt.warehouse_id=91;
 receipt.items[0].destination_type='WAREHOUSE';
 receipt.items[0].inventory_treatment='INVENTORY';
 receipt.destination_type='MIXED';
 await mount();
 const locationSelect=v.root.findByProps({'aria-label':'Location'});
 await renderer.act(async()=>locationSelect.props.onChange({target:{value:'2'}}));
 const physicalWarehouse=v.root.findByProps({'aria-label':'Physical Stock Warehouse'});
 assert.equal(physicalWarehouse.props.value,91,'changing historical reporting Location retains original physical warehouse');
 assert.ok(physicalWarehouse.props.options.some(row=>row.id===91),'original warehouse remains visible even when its location differs');
 assert.match(text(v.root),/original stock stays in WH-OLD/i,'warn that physical stock stays where it was');
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Department'}).props.onChange({target:{value:'1'}}));
 await renderer.act(async()=>v.root.findAllByType('textarea').find(n=>n.props.maxLength===500).props.onChange({target:{value:'Correct old reporting location without stock move'}}));
 await renderer.act(async()=>v.root.findAllByType('button').find(n=>text(n)==='Save Historical Correction').props.onClick());
 const correctedLocationPayload=global.__saved.at(-1).payload;
 assert.equal(correctedLocationPayload.location_id,2);
 assert.equal(correctedLocationPayload.warehouse_id,91,'history correction must preserve physical warehouse ID in payload');
 assert.equal(correctedLocationPayload.items.length,2);
 await renderer.act(async()=>v.unmount());
 console.log('Receiving edit PASS: draft editing, complete historical fields, and location change preserves stock warehouse.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});

