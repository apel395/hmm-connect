/* global require, __dirname, global, EventTarget, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require('node:assert/strict');
const root = require('node:path').resolve(__dirname, '..');
const req = require('node:module').createRequire(root + '/package.json');
const React = req('react'), renderer = req('react-test-renderer');
global.IS_REACT_ACT_ENVIRONMENT = true;
const values = new Map();
global.window = Object.assign(new EventTarget(), {localStorage: {getItem:k=>values.get(k)??null,setItem:(k,v)=>values.set(k,v),removeItem:k=>values.delete(k)}});
global.__owner = 45;
const item = {product_id:7,product_code:'7-000001',product_name:'Catering service',group_name:'SERVICE',uom:'PERIOD',selling_price:100,sale_available:true};
global.__queries = [];
global.__products = async params => {global.__queries.push(params);return {data:{items:params.page===1?[item]:[{...item,product_id:8}],has_next:params.page===1}};};
let writes = 0;
global.__api = {products:params=>global.__products(params),options:async()=>({data:{}}),create:async()=>{writes++;return {data:{id:1,transaction_number:'POS-1'}};},metadata:async()=>({data:{queue_number:'POS-1'}}),post:async()=>({data:{}})};
async function run() {
 const bundle=await req('esbuild').build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/pos/pages/PosRegisterPage.tsx'],bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime'],plugins:[{name:'mocks',setup(b){
 b.onResolve({filter:/^(?:@\/components\/|@\/store\/auth|@\/lib\/access|sonner|@tanstack\/react-query|react-router-dom|lucide-react|\.\.\/api)/},a=>({path:a.path,namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},a=>{
 let contents;
 if(a.path==='../api') contents='export const posApi=globalThis.__api;';
 else if(a.path==='@/store/auth') contents='export default selector=>selector({user:{id:globalThis.__owner}});';
 else if(a.path==='@/lib/access') contents='export const canAccess=()=>true;';
 else if(a.path==='sonner') contents='export const toast={success(){}};';
 else if(a.path==='react-router-dom') contents='export const useNavigate=()=>()=>{};';
 else if(a.path==='lucide-react') contents='export const Minus=()=>null,Plus=()=>null,Receipt=()=>null,ShoppingCart=()=>null,Trash2=()=>null;';
 else if(a.path==='@tanstack/react-query') contents=`export const useQueryClient=()=>({invalidateQueries:async()=>{}}); export const useQuery=o=>{globalThis.__queriesOptions??=[];globalThis.__queriesOptions.push(o);return {data:o.queryKey[0]==='pos-options'?{locations:[{id:6,name:'Rumin'},{id:8,name:'Hotel'}],departments:[{id:1,name:'Operations',location_id:6}]}:{items:[${JSON.stringify(item)}]},isLoading:false};};export const useMutation=o=>({isPending:false,mutate:async()=>{try{const result=await o.mutationFn();o.onSuccess?.(result);}catch(e){o.onError?.(e);}}});`;
 else if(a.path.includes('SearchableSelect')) contents=`import React from 'react';export default p=>React.createElement('select',{'aria-label':p.label,value:p.value??'',onChange:e=>p.onChange(e.target.value?Number(e.target.value):undefined)},React.createElement('option',{value:''},'All'),p.options.map(o=>React.createElement('option',{key:o.id,value:o.id},o.name)));`;
 else contents=`import React from 'react';export default ({children,onClick,disabled})=>React.createElement('${a.path.endsWith('/Button')?'button':'div'}',{onClick,disabled},children);`;
 return {contents,loader:'js'};
 });}}]});
 const m={exports:{}};new Function('module','exports','require',bundle.outputFiles[0].text)(m,m.exports,n=>req(n));
 const Page=m.exports.default;
 const mount=async()=>{let v;await renderer.act(async()=>{v=renderer.create(React.createElement(Page));});return v;};
 const text=n=>n.children.map(c=>typeof c==='string'?c:text(c)).join('');
 const button=(v,label)=>v.root.findAllByType('button').find(n=>text(n).includes(label));
 const click=async(v,label)=>{await renderer.act(async()=>{await button(v,label).props.onClick();});};
 let v=await mount();
 const query=global.__queriesOptions.find(o=>o.queryKey[0]==='pos-products');
 assert.notEqual(query.enabled,false,'menus load without a selected location');
 const result=await query.queryFn();assert.equal(result.items.length,2,'all menu pages are loaded');assert.equal(global.__queries[0].location_id,undefined);
 await click(v,'Catering service');
 await renderer.act(async()=>{v.root.findByProps({'aria-label':'Sales location'}).props.onChange({target:{value:'6'}});});
 assert.ok(text(v.root).includes('Rp 100'),'location filter preserves cart');
 await renderer.act(async()=>{v.root.findAllByType('input').find(n=>n.props.placeholder==='Contoh: M-01 / 12').props.onChange({target:{value:'12'}});});
 await renderer.act(async()=>v.unmount());
 v=await mount();
 assert.equal(v.root.findByProps({'aria-label':'Sales location'}).props.value,6);
 assert.equal(v.root.findAllByType('input').find(n=>n.props.placeholder==='Contoh: M-01 / 12').props.value,'12');
 assert.ok(button(v,'Clear'),'refresh restores cart');assert.equal(writes,0,'refresh never submits or posts');
 global.__owner=46;await renderer.act(async()=>v.update(React.createElement(Page)));
 assert.equal(button(v,'Clear'),undefined,'another user cannot recover this order');
 global.__owner=45;await renderer.act(async()=>v.update(React.createElement(Page)));
 await click(v,'Clear');await renderer.act(async()=>v.unmount());v=await mount();
 assert.equal(button(v,'Clear'),undefined,'explicit clear survives refresh');
 await click(v,'Catering service');await click(v,'Save Draft');
 await renderer.act(async()=>v.unmount());v=await mount();assert.equal(button(v,'Clear'),undefined,'saved draft does not return as unsaved cart');
 assert.equal(writes,1);
 await renderer.act(async()=>v.unmount());
 console.log('POS PASS: refresh recovery, user isolation, non-destructive filters, unfiltered paginated menus, explicit clear and saved draft cleanup.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
