/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict'),root=require('node:path').resolve(__dirname,'..'),req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');global.IS_REACT_ACT_ENVIRONMENT=true;
global.__setup={parents:[{id:7,name:'Food and Beverage'}],outlets:[{id:22,name:'Banquet',code:'BAN',parent_department_id:7,order_mode:'EVENT',is_active:false}]};global.__writes=[];global.__saved=[];
async function run(){
 const bundled=await req('esbuild').build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/pos/OutletSetup.tsx'],bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime'],plugins:[{name:'mocks',setup(b){
 b.onResolve({filter:/^(?:@\/components\/ui\/Button|@tanstack\/react-query|\.\/operationsApi)$/},a=>({path:a.path,namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},a=>({loader:'js',contents:a.path==='./operationsApi'?`export const operationsApi={outlets:async()=>({data:globalThis.__setup}),saveOutlet:async(values,id)=>{globalThis.__writes.push({values,id});return {data:{...values,id:id??99}}}};`:a.path==='@tanstack/react-query'?`export const useQueryClient=()=>({invalidateQueries:async()=>{}});export const useQuery=o=>({data:o.enabled?globalThis.__setup:undefined});export const useMutation=o=>({isPending:false,reset:()=>{},mutate:async()=>{const r=await o.mutationFn();await o.onSuccess(r);}});`:`import React from 'react';export default p=>React.createElement('button',p,p.children);`}));}}]});
 const m={exports:{}};new Function('module','exports','require',bundled.outputFiles[0].text)(m,m.exports,n=>req(n));const Page=m.exports.default;
 let v;await renderer.act(async()=>{v=renderer.create(React.createElement(Page,{locationId:8,userId:45,canManage:true,onSaved:id=>global.__saved.push(id)}));});
 const text=n=>n.children.map(c=>typeof c==='string'?c:text(c)).join('');
 const button=label=>v.root.findAllByType('button').find(n=>text(n)===label);
 await renderer.act(async()=>button('Manage F&B outlets').props.onClick());
 await renderer.act(async()=>v.root.findByProps({'aria-label':'Outlet name'}).props.onChange({target:{value:'Coffee Shop'}}));
 assert.equal(v.root.findByProps({'aria-label':'Outlet code'}).props.value,'COF');
 await renderer.act(async()=>v.root.findByProps({'aria-label':'New outlet order mode'}).props.onChange({target:{value:'COUNTER'}}));
 await renderer.act(async()=>button('Create outlet').props.onClick());
 assert.deepEqual(global.__writes[0],{values:{location_id:8,parent_department_id:7,name:'Coffee Shop',code:'COF',order_mode:'COUNTER',is_active:true},id:undefined});assert.deepEqual(global.__saved,[99]);
 await renderer.act(async()=>v.root.findAllByType('button').find(n=>text(n).includes('BAN')).props.onClick());
 assert.equal(v.root.findByProps({'aria-label':'Outlet code'}).props.value,'BAN');assert.equal(v.root.findByProps({'aria-label':'New outlet order mode'}).props.value,'EVENT');
 await renderer.act(async()=>button('Save outlet').props.onClick());assert.equal(global.__writes[1].id,22);assert.equal(global.__saved[1],undefined,'deactivation clears selected outlet');
 await renderer.act(async()=>v.unmount());
 await renderer.act(async()=>{v=renderer.create(React.createElement(Page,{locationId:8,canManage:false,onSaved:()=>{}}));});assert.equal(v.toJSON(),null,'cashier cannot see master-data setup');await renderer.act(async()=>v.unmount());

 console.log('Outlet setup PASS: inline create/edit, three-letter suggestion, selected outlet callback, inactive outlet handling, permission guard.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
