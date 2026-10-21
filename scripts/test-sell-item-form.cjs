/* eslint @typescript-eslint/no-require-imports: "off" */
/* global require, __dirname, global, console, process */
const assert=require('node:assert/strict');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const req=require('node:module').createRequire(root+'/package.json');
const React=req('react'), renderer=req('react-test-renderer');
global.IS_REACT_ACT_ENVIRONMENT=true;
async function run(){
 const {build}=req('esbuild');
 const result=await build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/master/products/components/ProductForm.tsx'],bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime'],plugins:[{name:'ui-services',setup(b){
  b.onResolve({filter:/^(@\/components\/ui\/Dialog|@\/components\/form\/SearchableSelect|@\/store\/auth|@tanstack\/react-query|@\/api\/client)$/},a=>({path:a.path,namespace:'stub'}));
  b.onLoad({filter:/.*/,namespace:'stub'},a=>({loader:'jsx',contents:
   a.path.includes('Dialog')?`import React from 'react'; const Box=({children})=><div>{children}</div>;export default Box; export const DialogBody=Box,DialogContent=Box,DialogFooter=Box,DialogHeader=Box,DialogTitle=Box;`:
   a.path.includes('SearchableSelect')?`import React from 'react'; export default p=><select aria-label={p.label} value={p.value||''} onChange={e=>p.onChange(e.target.value)}>{p.options.map(o=><option key={o.id} value={o.id}>{o.label||o.name}</option>)}</select>;`:
   a.path.includes('/auth')?`export const useAuthStore=selector=>selector({user:{id:1,roles:[{name:'SYSTEM_ADMINISTRATOR'}]}});export default useAuthStore;`:
   a.path.includes('react-query')?`export const useQuery=({queryKey})=>({data:queryKey[0]==='item-next-code'?{code:'5-000001'}:queryKey[0]==='item-departments'?{available:true,items:[]}:[],isLoading:false,isError:false});`:
   `export default {get:async()=>({data:[]})};`
  }));
 }}]});
 const mod={exports:{}};new Function('module','exports','require',result.outputFiles[0].text)(mod,mod.exports,req);
 let view,payload;
 await renderer.act(async()=>{view=renderer.create(React.createElement(mod.exports.default,{open:true,itemType:'SELL',groups:[{code:'5',name:'FOOD',item_type:'SELL',subgroups:[]}],onClose(){},onSubmit:p=>payload=p}));});
 const output=JSON.stringify(view.toJSON());
 for(const label of ['Purchase UOM','Usage UOM','Inventory Treatment','Posting COA','Conversion']) assert.ok(!output.includes(label),label);
 assert.ok(output.includes('Sales UOM'));
 const save=()=>view.root.findAllByType('button').find(b=>b.children.join('')==='Save');
 assert.equal(save().props.disabled,true);
 const input=(needle)=>view.root.findAllByType('input').find(i=>needle(i.props));
 await renderer.act(async()=>{
  input(p=>p.value==='' && p.maxLength===undefined && p.placeholder===undefined && !p.readOnly).props.onChange({target:{value:'Catering meal'}});
  view.root.findByProps({'aria-label':'Group'}).props.onChange({target:{value:'5'}});
 });
 assert.equal(save().props.disabled,true,'Sales UOM must be supplied');
 await renderer.act(async()=>{input(p=>p.placeholder?.includes('Portion, Meals')).props.onChange({target:{value:'Meals'}});});
 assert.equal(save().props.disabled,false,'One Sales UOM suffices; BUY usage UOM and accounting fields are absent');
 await renderer.act(async()=>save().props.onClick());
 assert.equal(payload.item_type,'SELL');assert.equal(payload.name,'Catering meal');
 assert.equal(payload.uom,'Meals');assert.equal(payload.usage_uom,'Meals');assert.equal(payload.conversion,1);
 assert.equal(payload.inventory_treatment,'NON_STOCK');
 for(const key of ['inventory_account_id','purchase_account_id','asset_account_id','cogs_account_id']) assert.equal(payload[key],null);
 await renderer.act(async()=>view.unmount());
 console.log('SELL form: single sales unit enables Save; inventory, expense and COGS mappings absent.');
}
run().catch(e=>{console.error(e);process.exit(1);});
