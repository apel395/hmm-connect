/* global require, __dirname, global, EventTarget, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict'),root=require('node:path').resolve(__dirname,'..'),req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');global.IS_REACT_ACT_ENVIRONMENT=true;
const values=new Map();global.window=Object.assign(new EventTarget(),{localStorage:{getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}});
global.__params='location=8&outlet=21';global.__sale=null;
const item={product_id:7,product_code:'5-000001',product_name:'Hotel meal',group_name:'FOOD',uom:'PLATE',selling_price:100,tax_type:'PBJT',tax_rate:10,is_taxable:true,service_charge_rate:0,sale_available:true,catalog_type:'HOTEL'};
global.__checkout={version:'checkout-v1',configured:true,configuration:{discount_presets:[{id:'member',name:'Member',kind:'PERCENT',value:'10',enabled:true}],payment_methods:[{method:'CASH',enabled:true,account_id:1},{method:'CARD',enabled:false,account_id:null},{method:'BANK_TRANSFER',enabled:true,account_id:2}]}};
global.__op={order_mode:'TABLE',tables:[{id:3,name:'T-03',seats:2,is_active:true,status:'AVAILABLE'}],shifts:[],orders:[]};
const writes=[],posts=[],updates=[];let failPost=true;
global.__api={detail:async()=>({data:global.__sale}),create:async p=>{writes.push(p);return {data:{id:88,transaction_number:'POS-88',table_number:p.pos_table_id?'T-03':null,cashier_session_id:p.cashier_session_id}};},update:async(id,p)=>{updates.push({id,p});return {data:{id,transaction_number:'POS-88',table_number:global.__sale?.table_number??'T-03',cashier_session_id:5}};},metadata:async()=>({data:{transaction_number:'POS-88'}}),post:async(id,p)=>{posts.push({id,p});if(failPost)throw Error('Network failed');return {data:{status:'POSTED'}};}};
async function run(){
 const decimalBundle=await req('esbuild').build({absWorkingDir:root,entryPoints:['src/modules/pos/checkoutTypes.ts'],bundle:true,write:false,platform:'node',format:'cjs'});const decimal={exports:{}};new Function('module','exports',decimalBundle.outputFiles[0].text)(decimal,decimal.exports);
 assert.equal(decimal.exports.discountFor(100.05,{kind:'PERCENT',value:'10'}),10.01,'half cents follow Decimal HALF_UP');assert.equal(decimal.exports.discountFor(0.05,{kind:'PERCENT',value:'10'}),0.01);assert.equal(decimal.exports.discountFor(99.95,{kind:'PERCENT',value:'7.5'}),7.50);
 const bundle=await req('esbuild').build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/pos/pages/PosRegisterPage.tsx'],bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime'],plugins:[{name:'mocks',setup(b){
 b.onResolve({filter:/^(?:@\/components\/|@\/store\/auth|@\/lib\/access|sonner|@tanstack\/react-query|react-router-dom|lucide-react|\.\.\/api|\.\.\/operationsApi|\.\.\/components\/PosCustomerField)/},a=>({path:a.path,namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},a=>{let contents;
 if(a.path==='../api')contents='export const posApi=globalThis.__api;';
 else if(a.path==='../operationsApi')contents='export const operationsApi={};';
 else if(a.path==='@/store/auth')contents='export default s=>s({user:{id:45}});';
 else if(a.path==='@/lib/access')contents='export const canAccess=()=>true;';
 else if(a.path==='sonner')contents='export const toast={success(){}};';
 else if(a.path==='react-router-dom')contents="import React from 'react';export const useNavigate=()=>()=>{};export const useSearchParams=()=>[new URLSearchParams(globalThis.__params)];export const Link=p=>React.createElement('a',{href:p.to},p.children);";
 else if(a.path==='lucide-react')contents='export const Minus=()=>null,Plus=()=>null,Receipt=()=>null,ShoppingCart=()=>null,Trash2=()=>null,CopyPlus=()=>null;';
 else if(a.path==='@tanstack/react-query')contents=`export const useQueryClient=()=>({invalidateQueries:async()=>{}});export const useQuery=o=>({data:o.queryKey[0]==='pos-continue'?globalThis.__sale:o.queryKey[0]==='pos-checkout'?globalThis.__checkout:o.queryKey[0]==='pos-operations'?globalThis.__op:o.queryKey[0]==='pos-options'?{locations:[{id:8,name:'Hotel',catalog_type:'HOTEL',has_outlets:true}],departments:[{id:21,name:'Restaurant',location_id:8,is_outlet:true,is_fnb_outlet:true},{id:22,name:'Cafe',location_id:8,is_outlet:true,is_fnb_outlet:true}]}:o.queryKey[0]==='pos-revenue-accounts'?[{id:37,name:'Revenue'}]:{items:[${JSON.stringify(item)}]},isLoading:false});export const useMutation=o=>({isPending:false,mutate:async()=>{try{const r=await o.mutationFn();o.onSuccess?.(r);}catch(e){o.onError?.(e);}}});`;
 else if(a.path.includes('SearchableSelect'))contents=`import React from 'react';export default p=>React.createElement('select',{'aria-label':p.label,value:p.value??'',disabled:p.disabled,onChange:e=>p.onChange(e.target.value?Number(e.target.value):undefined)},p.options.map(o=>React.createElement('option',{key:o.id,value:o.id},o.name)));`;
 else if(a.path==='../components/PosCustomerField')contents='export default ()=>null;';
 else contents=`import React from 'react';export default p=>React.createElement('${a.path.endsWith('/Button')?'button':'div'}',{onClick:p.onClick,disabled:p.disabled},p.children);`;
 return {contents,loader:'js'};});}}]});
 const m={exports:{}};new Function('module','exports','require',bundle.outputFiles[0].text)(m,m.exports,n=>req(n));const Page=m.exports.default;
 const text=n=>n.children.map(c=>typeof c==='string'?c:text(c)).join('');
 const mount=async()=>{let v;await renderer.act(async()=>{v=renderer.create(React.createElement(Page));});return v;};
 const click=async(v,label)=>renderer.act(async()=>{const b=v.root.findAllByType('button').find(n=>text(n).includes(label));assert.ok(b,label);assert.ok(!b.props.disabled,label+' is enabled');await b.props.onClick();});
 let v=await mount();
 const mealButton=()=>v.root.findAllByType('button').find(n=>text(n).includes('Hotel meal'));
 assert.equal(mealButton().props.disabled,true,'choose table before menu');
 assert.equal(v.root.findByProps({'aria-label':'Number of guests'}).props.disabled,true,'table comes before people');
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Table'}).props.onChange({target:{value:'3'}}));
 for(const count of ['', '0','-1','1.5']){
   await renderer.act(async()=>v.root.findByProps({'aria-label':'Number of guests'}).props.onChange({target:{value:count}}));
   assert.equal(mealButton().props.disabled,true,'invalid or missing count cannot add menus');
 }
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Number of guests'}).props.onChange({target:{value:'2'}}));
 await click(v,'Hotel meal');await renderer.act(async()=>v.root.findByProps({'aria-label':'Revenue account'}).props.onChange({target:{value:'37'}}));
 await click(v,'Save Draft');assert.equal(writes.length,0,'shift required');
 global.__op.shifts=[{id:5,cashier_id:45,status:'OPEN'}];await renderer.act(async()=>v.update(React.createElement(Page)));
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Table'}).props.onChange({target:{value:''}}));
 await click(v,'Save Draft');assert.equal(writes.length,0,'table required');
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Table'}).props.onChange({target:{value:'3'}}));
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Hotel outlet'}).props.onChange({target:{value:'22'}}));
 assert.equal(v.root.findByProps({'aria-label':'Hotel outlet'}).props.value,21,'active cart pins outlet');
 await renderer.act(async()=>v.root.findAllByType('input').find(i=>i.props.placeholder==='Cash received').props.onChange({target:{value:'110'}}));
 assert.equal(v.root.findByProps({'aria-label':'Discount preset'}).type,'select','Hotel discount is selected, not typed');
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Discount preset'}).props.onChange({target:{value:'member'}}));
 assert.ok(text(v.root).includes('Rp 99'),'preset recalculates amount and PBJT');
 assert.ok(!v.root.findByProps({'aria-label':'Payment method'}).findAllByType('option').some(o=>o.props.value==='CARD'),'disabled payment is hidden');
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Payment method'}).props.onChange({target:{value:'CARD'}}));
 await click(v,'Ambil Nomor & Bayar');assert.equal(writes.length,0,'forged disabled payment cannot create or settle');
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Payment method'}).props.onChange({target:{value:'CASH'}}));
 await click(v,'Ambil Nomor & Bayar');assert.equal(writes.length,1);assert.equal(writes[0].pos_table_id,3);assert.equal(writes[0].guest_count,2);assert.equal(writes[0].cashier_session_id,5);assert.ok(writes[0].order_request_key);assert.equal(writes[0].discount_preset_id,'member');assert.equal(writes[0].checkout_version,'checkout-v1');assert.equal(posts[0].p.discount_amount,undefined,'Hotel does not submit an arbitrary discount amount');
 await renderer.act(async()=>v.unmount());v=await mount();failPost=false;assert.equal(v.root.findByProps({'aria-label':'Number of guests'}).props.value,'2','refresh restores guest count');
 await click(v,'Ambil Nomor & Bayar');assert.equal(writes.length,1,'retry reuses order ID after refresh');assert.equal(updates.at(-1).id,88);assert.equal(posts.length,2);
 await renderer.act(async()=>v.unmount());
 global.__params='order=91';global.__sale={id:91,transaction_number:'POS-91',status:'DRAFT',transaction_type:'POS',location_id:8,department_id:21,cashier_session_id:5,pos_table_id:3,guest_count:3,table_number:'T-03',revenue_account_id:37,items:[{...item,quantity:2,unit_price:100,product_name:'Saved meal'}]};
 v=await mount();assert.ok(text(v.root).includes('Saved meal'),'continue loads saved order');assert.equal(v.root.findByProps({'aria-label':'Number of guests'}).props.value,'3','continue loads server guest count');await renderer.act(async()=>v.root.findByProps({'aria-label':'Number of guests'}).props.onChange({target:{value:'4'}}));await click(v,'Hotel meal');await renderer.act(async()=>v.root.findAllByType('input').find(i=>i.props.placeholder==='Cash received').props.onChange({target:{value:'330'}}));
 await click(v,'Ambil Nomor & Bayar');assert.equal(writes.length,1);assert.equal(updates.at(-1).id,91);assert.equal(updates.at(-1).p.guest_count,4);assert.equal(updates.at(-1).p.items[0].quantity,3,'continue can add items to existing order');
 await renderer.act(async()=>v.unmount());global.__sale.status='POSTED';v=await mount();assert.ok(text(v.root).includes('cannot be continued'),'posted order not editable');await renderer.act(async()=>v.unmount());
 values.clear();global.__params='location=8&outlet=21';global.__op.order_mode='EVENT';v=await mount();assert.equal(v.root.findAllByProps({'aria-label':'Table'}).length,0);await click(v,'Hotel meal');await renderer.act(async()=>v.root.findByProps({'aria-label':'Revenue account'}).props.onChange({target:{value:'37'}}));await click(v,'Save Draft');assert.equal(writes.length,1,'event name required');await renderer.act(async()=>v.root.findByProps({'aria-label':'Event name'}).props.onChange({target:{value:'Annual Dinner'}}));await click(v,'Save Draft');assert.equal(writes.at(-1).event_name,'Annual Dinner');assert.equal(writes.at(-1).pos_table_id,undefined);assert.equal(writes.at(-1).guest_count,null,'banquet guest count optional');await renderer.act(async()=>v.unmount());
 values.clear();global.__op.order_mode='COUNTER';v=await mount();assert.equal(v.root.findByProps({'aria-label':'Number of guests'}).props.value,'');await click(v,'Hotel meal');await renderer.act(async()=>v.root.findByProps({'aria-label':'Revenue account'}).props.onChange({target:{value:'37'}}));await click(v,'Save Draft');assert.equal(writes.at(-1).guest_count,null,'counter guests are optional');assert.equal(writes.at(-1).pos_table_id,undefined,'counter table is optional');await renderer.act(async()=>v.unmount());
 console.log('Outlet POS PASS: table → people → menu, optional counter/event guests, required shift/table/event, pinned outlet, stable draft retry, continued order adds items and settles without creating duplicates.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
