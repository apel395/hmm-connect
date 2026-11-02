/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict');
const {setTimeout}=require('node:timers');
const root=require('node:path').resolve(__dirname,'..');
const req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');
const {QueryClient,QueryClientProvider}=req('@tanstack/react-query');
global.IS_REACT_ACT_ENVIRONMENT=true;global.__pphSaves=[];
async function bundle(path,plugins=[]) {
 const r=await req('esbuild').build({absWorkingDir:root,entryPoints:[path],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime','@tanstack/react-query'],plugins});
 const m={exports:{}};new Function('require','module','exports',r.outputFiles[0].text)(req,m,m.exports);return m.exports;
}
async function run(){
 const rules=await bundle('src/modules/finance/fixed-assets/categoryRules.ts');
 const accounts=[{id:215,account_code:'100-600-104'},{id:216,account_code:'100-600-105'},{id:222,account_code:'100-800-103'},{id:223,account_code:'100-800-104'},{id:84,account_code:'700-500-133'}];
 const c={id:2,fiscal_group_code:'GROUP_2',asset_account_id:null,is_depreciable:true,default_useful_life_months:96};
 for(const id of [215,216]){
  const f=rules.categoryDefaults({asset_account_id:id,acquisition_cost:'5500000'},c,accounts);
  assert.equal(f.asset_account_id,id,'Fiscal groups retain the actual asset COA');
  assert.equal(f.accumulated_depreciation_account_id,id===215?222:223);
  assert.equal(f.depreciation_expense_account_id,84);assert.equal(f.useful_life_months,96);assert.equal(f.acquisition_cost,'5500000');
 }
 assert.equal(rules.groupAcceptsAccount('GROUP_2','100-600-101'),false);
 assert.equal(rules.groupAcceptsAccount('LAND','100-600-104'),false);
 assert.equal(rules.groupAcceptsAccount('BUILDING_PERMANENT','100-600-101'),true);
 const groups=[{code:'GROUP_1',name:'Kelompok 1',months:48,straight_line_rate:'25',declining_balance_rate:'50'}, {code:'GROUP_2',name:'Kelompok 2',months:96,straight_line_rate:'12.5',declining_balance_rate:'25'}];
 global.__pphData=[{id:1,code:'PPH-G1',name:'Kelompok 1',fiscal_group_code:'GROUP_1',default_useful_life_months:48,straight_line_rate:'25',declining_balance_rate:'50',is_active:true,creator:'System migration'},
 {id:3,code:'FA-0001',name:'User category',fiscal_group_code:null,default_useful_life_months:48,is_active:true,creator:'Finance'},
 {id:4,code:'MMH-FFE',name:'Old script default',is_active:false,fiscal_group_code:null,source:'MMH_SETUP_SCRIPT'}];
 global.__pphGroups=groups;
 const Page=(await bundle('src/modules/finance/fixed-assets/AssetCategoryPage.tsx',[{name:'fixtures',setup(b){
  b.onResolve({filter:/^(\.\/api|@\/components\/|sonner$|lucide-react$)/},a=>({path:a.path,namespace:'mock'}));
  b.onLoad({filter:/.*/,namespace:'mock'},a=>({loader:'js',contents:a.path==='./api'?`export const listCategories=async()=>globalThis.__pphData;export const listFiscalGroups=async()=>globalThis.__pphGroups;export const saveCategory=async data=>{globalThis.__pphSaves.push(data);return data}`:a.path==='sonner'?`export const toast={success(){},error(){}}`:a.path==='lucide-react'?`export const Plus=()=>null,Printer=()=>null`:a.path.endsWith('PageHeader')?`import React from 'react';export default p=>React.createElement('header',null,p.title,p.actions)`:a.path.endsWith('/Table')?`import React from 'react';export const Table=p=>React.createElement('table',null,p.children),THead=p=>React.createElement('thead',null,p.children),TBody=p=>React.createElement('tbody',null,p.children),TR=p=>React.createElement('tr',null,p.children),TH=p=>React.createElement('th',null,p.children),TD=p=>React.createElement('td',null,p.children)`:`import React from 'react';export default p=>React.createElement(${a.path.endsWith('/Button')?"'button'":"'section'"},p,p.children)`}));
 }}])).default;
 const client=new QueryClient({defaultOptions:{queries:{retry:false}}});let tree;
 await renderer.act(async()=>{tree=renderer.create(React.createElement(QueryClientProvider,{client},React.createElement(Page)));await new Promise(r=>setTimeout(r,20))});
 await renderer.act(async()=>{await new Promise(r=>setTimeout(r,20))});
 let output=JSON.stringify(tree.toJSON());assert.ok(output.includes('User category'));assert.ok(!output.includes('Old script default'));
 assert.ok(output.includes('25%')&&output.includes('50%'));
 await renderer.act(async()=>tree.root.findByType('input').props.onChange({target:{checked:true}}));
 assert.ok(JSON.stringify(tree.toJSON()).includes('Old script default'));
 await renderer.act(async()=>tree.root.findAllByType('button').find(b=>b.children.includes('Category')).props.onClick());
 await renderer.act(async()=>tree.root.findByType('select').props.onChange({target:{value:'GROUP_2'}}));
 const inputs=tree.root.findAllByType('input');
 await renderer.act(async()=>inputs.find(x=>x.props.maxLength===30).props.onChange({target:{value:'PPH-TEST'}}));
 assert.ok(!JSON.stringify(tree.toJSON()).includes('Disposal gain account'));
 await renderer.act(async()=>tree.root.findAllByType('button').find(b=>b.children.includes('Save category')).props.onClick());
 assert.equal(global.__pphSaves[0].fiscal_group_code,'GROUP_2');assert.equal(global.__pphSaves[0].default_useful_life_months,96);
 assert.equal(global.__pphSaves[0].asset_account_id,null);
 await renderer.act(async()=>tree.unmount());client.clear();
 console.log('PPh category UI PASS: rates, user categories retained, inactive defaults hidden, per-asset COA and group-driven defaults');
}
run().catch(e=>{console.error(e);process.exit(1)});
