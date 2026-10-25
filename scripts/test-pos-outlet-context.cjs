/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict'),root=require('node:path').resolve(__dirname,'..'),req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');global.IS_REACT_ACT_ENVIRONMENT=true;
global.__params='location=6&outlet=1';
global.__options={locations:[{id:6,name:'Rumin',catalog_type:'CATERING'},{id:8,name:'Hotel',catalog_type:'HOTEL',has_outlets:true}],departments:[{id:1,name:'Operations',location_id:6},{id:21,name:'Restaurant',location_id:8,is_outlet:true},{id:31,name:'Other hotel outlet',location_id:9,is_outlet:true}]};
global.__context={order_mode:null,tables:[],shifts:[],orders:[]};global.__queries=[];global.__loading=false;global.__failed=false;global.__calls=[];
async function run(){
 const bundled=await req('esbuild').build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/pos/pages/PosOperationsPage.tsx'],bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime'],plugins:[{name:'mocks',setup(b){
 b.onResolve({filter:/^(?:@\/components\/|@\/store\/auth|@tanstack\/react-query|react-router-dom|lucide-react|\.\.\/api|\.\.\/operationsApi)/},a=>({path:a.path,namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},a=>{let contents;
 if(a.path==='../api')contents='export const posApi={options:async()=>({data:globalThis.__options})};';
 else if(a.path==='../operationsApi')contents="export const operationsApi={context:async scope=>{globalThis.__calls.push(scope);return {data:globalThis.__context};},report:async()=>({data:{}})};";
 else if(a.path==='@/store/auth')contents='export default s=>s({user:{id:45},hasPermission:()=>true});';
 else if(a.path==='react-router-dom')contents="import React from 'react';export const useSearchParams=()=>[new URLSearchParams(globalThis.__params),(values)=>{globalThis.__params=new URLSearchParams(values).toString();}];export const Link=p=>React.createElement('a',{href:p.to},p.children);";
 else if(a.path==='lucide-react')contents='export const Printer=()=>null;';
 else if(a.path==='@tanstack/react-query')contents="export const useQueryClient=()=>({invalidateQueries:async()=>{}});export const useMutation=()=>({isPending:false});export const useQuery=o=>{globalThis.__queries.push(o);if(o.queryKey[0]==='pos-options')return {data:globalThis.__loading?undefined:globalThis.__options,isLoading:globalThis.__loading};return {data:o.enabled&&!globalThis.__failed?globalThis.__context:undefined,isLoading:false,isError:Boolean(o.enabled&&globalThis.__failed),error:{response:{data:{detail:'Outlet is unavailable'}}}};};";
 else if(a.path.includes('SearchableSelect'))contents="import React from 'react';export default p=>React.createElement('select',{'aria-label':p.label,value:p.value??'',onChange:e=>p.onChange(e.target.value?Number(e.target.value):undefined)},p.options.map(o=>React.createElement('option',{key:o.id,value:o.id},o.name)));";
 else contents="import React from 'react';export default p=>React.createElement('div',null,p.children);";
 return {contents,loader:'js'};});}}]});
 const m={exports:{}};new Function('module','exports','require',bundled.outputFiles[0].text)(m,m.exports,n=>req(n));const Page=m.exports.default;
 const mount=async()=>{let v;global.__queries=[];await renderer.act(async()=>{v=renderer.create(React.createElement(Page));});return v;};
 const text=n=>n.children.map(c=>typeof c==='string'?c:text(c)).join('');
 const lastQuery=()=>global.__queries.filter(q=>q.queryKey[0]==='pos-operations').at(-1);
 let v=await mount();assert.equal(lastQuery().enabled,false,'Catering URL cannot trigger Hotel operations');assert.equal(v.root.findByProps({'aria-label':'Hotel location'}).props.value,'');assert.ok(!text(v.root).includes('Configure TABLE'),'invalid selection is not unconfigured outlet');assert.ok(!text(v.root).includes('migration'),'invalid selection is not a schema failure');
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Hotel location'}).props.onChange({target:{value:'8'}}));assert.equal(lastQuery().enabled,false,'outlet must also be chosen');
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Outlet'}).props.onChange({target:{value:'21'}}));assert.equal(lastQuery().enabled,true);await lastQuery().queryFn();assert.deepEqual(global.__calls.at(-1),{location_id:8,department_id:21});assert.equal(global.__params,'location=8&outlet=21','valid selection replaces stale URL');assert.ok(text(v.root).includes('Configure TABLE'),'successfully loaded empty policy shows Setup');await renderer.act(async()=>v.unmount());
 global.__params='location=8&outlet=31';v=await mount();assert.equal(lastQuery().enabled,false,'child outlet belonging to another location is rejected');await renderer.act(async()=>v.unmount());
 global.__params='location=8&outlet=21';global.__loading=true;v=await mount();assert.equal(lastQuery().enabled,false,'wait for accessible options before trusting URL');assert.ok(text(v.root).includes('Loading Hotel locations'));await renderer.act(async()=>v.unmount());global.__loading=false;
 global.__failed=true;v=await mount();assert.ok(text(v.root).includes('Outlet is unavailable'));assert.ok(!text(v.root).includes('Configure TABLE'),'request failure must not suggest configuring an unknown policy');assert.ok(!text(v.root).includes('migration'),'show real error rather than inventing migration cause');await renderer.act(async()=>v.unmount());global.__failed=false;
 global.__params='location=8';global.__options.departments=[];global.__options.locations[1].has_outlets=false;v=await mount();assert.equal(v.root.findByProps({'aria-label':'Hotel location'}).props.value,8,'Hotel remains selectable before outlets are configured');assert.ok(text(v.root).includes('No child outlets'));assert.equal(lastQuery().enabled,false);await renderer.act(async()=>v.unmount());
 console.log('Outlet context PASS: invalid Catering/cross-location URLs blocked, options-loading guard, URL selection retained, setup/error states distinguished.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
