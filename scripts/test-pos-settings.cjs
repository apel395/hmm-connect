/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict'),root=require('node:path').resolve(__dirname,'..'),req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');global.IS_REACT_ACT_ENVIRONMENT=true;
global.__params='location=6';global.__permissions=['pos.view','finance.manage'];global.__queries=[];global.__writes=[];
const profile={configuration:{customer_id:9,department_id:1,revenue_account_id:37,receivable_account_id:38,payment_term_days:30,service_product_ids:[7],billing:{template:'phr',title:'INVOICE',billing_name:'Pertamina Site',billing_address:'Site Address',attention:'AP',contract_number:'SITE-6',contract_date:null,company_address:'',payment_instructions:'Bank details',footer:'',signer_name:'',signer_position:''}},can_manage:true,service_choices:[{id:7,name:'Catering service'}]};
global.__data={
 'pos-options':{locations:[{id:6,name:'Catering',catalog_type:'CATERING'},{id:8,name:'Hotel',catalog_type:'HOTEL'}],departments:[{id:1,name:'Operations',location_id:6},{id:21,name:'Restaurant',location_id:8,is_outlet:true,is_fnb_outlet:true}]},
 'catering-billing':profile,'pos-billing-options':{customers:[{id:9,name:'Pertamina Site'}],receivable_accounts:[{id:38,name:'AR'}]},'pos-revenue-accounts':[{id:37,name:'Revenue'}],
 'pos-operations':{order_mode:'TABLE',tables:[{id:1,name:'T1',seats:2,is_active:true,status:'AVAILABLE'},{id:2,name:'T2',seats:4,is_active:true,status:'OCCUPIED'}],orders:[],shifts:[]},
 'pos-checkout-settings':{version:'checkout-v1',configured:false,configuration:{discount_presets:[],payment_methods:[{method:'CASH',enabled:true,account_id:38},{method:'CARD',enabled:false,account_id:null},{method:'BANK_TRANSFER',enabled:false,account_id:null}]},accounts:[{id:38,name:'Cash'}]},
 'pos-outlet-setup':{parents:[{id:10,name:'Food & Beverage'}],outlets:[]}
};
async function run(){
 const bundled=await req('esbuild').build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/pos/pages/PosSettingsPage.tsx'],bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime'],plugins:[{name:'mocks',setup(b){
 b.onResolve({filter:/^(?:@\/components\/|@\/store\/auth|@tanstack\/react-query|react-router-dom|\.\.\/api|\.{1,2}\/operationsApi)/},a=>({path:a.path,namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},a=>{let contents;
 if(a.path==='../api')contents='export const posApi={saveCateringSettings:async(id,data)=>{globalThis.__writes.push({kind:"billing",id,data});return {data:{}};}};';
 else if(a.path.endsWith('/operationsApi'))contents='export const operationsApi={saveCheckoutSettings:async(scope,configuration,version)=>{globalThis.__writes.push({kind:"checkout",scope,configuration,version});return {data:{configuration,version:"checkout-v2"}};},policy:async(scope,mode)=>{globalThis.__writes.push({kind:"policy",scope,mode});},table:async(scope,data,id)=>{globalThis.__writes.push({kind:"table",scope,data,id});}};';
 else if(a.path==='@/store/auth')contents='export default s=>s({user:{id:45,roles:[{name:"CUSTOM_ADMIN",permissions:globalThis.__permissions.map(code=>({code}))}]}});';
 else if(a.path==='react-router-dom')contents='import React from "react";export const useSearchParams=()=>[new URLSearchParams(globalThis.__params),(value)=>{globalThis.__params=new URLSearchParams(value).toString();}];export const useNavigate=()=>()=>{};export const Link=p=>React.createElement("a",{href:p.to},p.children);';
 else if(a.path==='@tanstack/react-query')contents='export const useQueryClient=()=>({invalidateQueries:async()=>{}});export const useQuery=o=>{globalThis.__queries.push(o);return {data:o.enabled===false?undefined:globalThis.__data[o.queryKey[0]],isLoading:false,isError:false};};export const useMutation=o=>({isPending:false,mutate:async args=>{try{const result=await o.mutationFn(args);o.onSuccess?.(result);}catch(e){o.onError?.(e);}},reset(){}});';
 else if(a.path.includes('SearchableSelect'))contents='import React from "react";export default p=>React.createElement("select",{"aria-label":p.label,value:p.value??"",onChange:e=>p.onChange(e.target.value?Number(e.target.value):undefined)},p.options.map(o=>React.createElement("option",{key:o.id,value:o.id},o.name)));';
 else contents='import React from "react";export default ({children,onClick,disabled})=>React.createElement("button",{onClick,disabled},children);';
 return {contents,loader:'js'};});}}]});
 const m={exports:{}};new Function('module','exports','require',bundled.outputFiles[0].text)(m,m.exports,n=>req(n));
 const Page=m.exports.default,mount=async()=>{let v;await renderer.act(async()=>{v=renderer.create(React.createElement(Page));});return v;},text=n=>n.children.map(c=>typeof c==='string'?c:text(c)).join('');
 const button=(v,label)=>v.root.findAllByType('button').find(n=>text(n)===label);
 let v=await mount();assert.equal(v.root.findAllByProps({'aria-label':'Catering location billing settings'}).length,1);
 assert.ok(v.root.findAllByType('input').some(n=>n.props.value==='SITE-6'));
 await renderer.act(async()=>button(v,'Save location defaults').props.onClick());assert.equal(global.__writes[0].kind,'billing');assert.equal(global.__writes[0].id,6);
 assert.equal(global.__writes[0].data.billing.contract_number,'SITE-6');await renderer.act(async()=>v.unmount());
 global.__params='location=8&outlet=21';v=await mount();assert.ok(text(v.root).includes('Outlet orders and tables'));
 await renderer.act(async()=>{v.root.findByProps({'aria-label':'Outlet order mode'}).props.onChange({target:{value:'COUNTER'}});});
 await renderer.act(async()=>button(v,'Save mode').props.onClick());assert.deepEqual(global.__writes.at(-1),{kind:'policy',scope:{location_id:8,department_id:21},mode:'COUNTER'});
 await renderer.act(async()=>button(v,'Add discount preset').props.onClick());
 assert.equal(button(v,'Save checkout settings').props.disabled,true,'new preset needs an explicit approved name/value');
 await renderer.act(async()=>{v.root.findByProps({'aria-label':'Discount name 1'}).props.onChange({target:{value:'Member'}});});
 await renderer.act(async()=>{v.root.findByProps({'aria-label':'Discount value 1'}).props.onChange({target:{value:'10'}});});
 await renderer.act(async()=>button(v,'Save checkout settings').props.onClick());assert.equal(global.__writes.at(-1).kind,'checkout');assert.equal(global.__writes.at(-1).version,'checkout-v1');assert.equal(global.__writes.at(-1).configuration.discount_presets[0].value,'10');assert.equal(global.__writes.at(-1).configuration.payment_methods[0].account_id,38);
 const edits=v.root.findAllByType('button').filter(n=>text(n)==='Edit');assert.equal(edits[0].props.disabled,false);assert.equal(edits[1].props.disabled,true,'occupied tables retain protection');
 await renderer.act(async()=>edits[0].props.onClick());assert.equal(v.root.findByProps({'aria-label':'Table name'}).props.value,'T1');
 await renderer.act(async()=>button(v,'Save table').props.onClick());assert.equal(global.__writes.at(-1).id,1);assert.equal(global.__writes.at(-1).scope.department_id,21);await renderer.act(async()=>v.unmount());
 global.__permissions=['pos.view'];global.__queries=[];v=await mount();assert.ok(text(v.root).includes('do not have permission'));assert.equal(global.__queries.length,0,'cashiers do not load setting controls');await renderer.act(async()=>v.unmount());
 global.__permissions=['pos.view','admin.settings.manage'];v=await mount();assert.ok(!text(v.root).includes('Outlet orders and tables'));assert.ok(text(v.root).includes('Finance management permission'));await renderer.act(async()=>v.unmount());
 global.__params='location=999';global.__queries=[];v=await mount();assert.ok(text(v.root).includes('Choose a sales location'));assert.equal(global.__queries.find(q=>q.queryKey[0]==='catering-billing').enabled,false);await renderer.act(async()=>v.unmount());
 console.log('POS Settings PASS: location/customer defaults, Finance policy/table editing, occupied-table protection, explicit permission gates and untrusted location handling.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
