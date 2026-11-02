/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require('node:assert/strict');
const { setTimeout } = require('node:timers');
const root = require('node:path').resolve(__dirname, '..');
const req = require('node:module').createRequire(root + '/package.json');
const React = req('react'), renderer = req('react-test-renderer');
const {QueryClient, QueryClientProvider} = req('@tanstack/react-query');
global.IS_REACT_ACT_ENVIRONMENT = true;
global.__assetFiscalSaves = [];
const profile = {group_code:'GROUP_1',method:'STRAIGHT_LINE',fiscal_cost:'4800',start_date:'2026-10-01',useful_life_months:null,reference:'Invoice',opening_date:null,opening_book_value:null,version:1};
const groups = [{code:'GROUP_1',name:'Group 1',months:48,straight_line_rate:'25',declining_balance_rate:'50'}, {code:'BUILDING_PERMANENT',name:'Building',months:240,straight_line_rate:'5',declining_balance_rate:null}, {code:'LAND',name:'Land',months:null}];
global.__assetFiscalData = {profile,groups,schedule:[]};
async function run() {
  const build = await req('esbuild').build({absWorkingDir:root,entryPoints:['src/modules/finance/fixed-assets/AssetFiscalPanel.tsx'],bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime','@tanstack/react-query'],plugins:[{name:'fixtures',setup(b){
    b.onResolve({filter:/^(\.\/api|@\/components\/ui\/Button|sonner)$/},a=>({path:a.path,namespace:'mock'}));
    b.onLoad({filter:/.*/,namespace:'mock'},a=>({loader:'js',contents:a.path==='./api' ? `export const getFiscalProfile=async()=>globalThis.__assetFiscalData;export const saveFiscalProfile=async(id,data)=>{globalThis.__assetFiscalSaves.push({id,data});return data};` : a.path==='sonner' ? `export const toast={success:()=>{},error:()=>{}}` : `import React from 'react'; export default function Button(p){return React.createElement('button',p,p.children)}`}));
  }}]});
  const module = {exports:{}}; new Function('require','module','exports',build.outputFiles[0].text)(req,module,module.exports);
  const Panel = module.exports.default, client = new QueryClient({defaultOptions:{queries:{retry:false}}});
  let tree;
  await renderer.act(async()=>{tree=renderer.create(React.createElement(QueryClientProvider,{client},React.createElement(Panel,{asset:{id:7,acquisition_cost:'4800',acquisition_date:'2026-10-01'}})))});
  await renderer.act(async()=>{tree.root.findAllByType('button')[0].props.onClick(); await new Promise(r=>setTimeout(r,20));});
  await renderer.act(async()=>{await new Promise(r=>setTimeout(r,20));});
  const configure=tree.root.findAllByType('button').find(b=>b.children.includes('Configure'));
  assert.ok(configure,'Fiscal setup loads only after expansion');
  await renderer.act(async()=>configure.props.onClick());
  let select=tree.root.findAllByType('select')[0];
  await renderer.act(async()=>select.props.onChange({target:{value:'BUILDING_PERMANENT'}}));
  assert.equal(tree.root.findAllByType('select')[1].findAllByType('option').length,1,'Buildings cannot select declining balance');
  await renderer.act(async()=>tree.root.findAllByType('select')[0].props.onChange({target:{value:'LAND'}}));
  assert.equal(tree.root.findAllByType('select')[1].props.value,'NONE');
  assert.equal(tree.root.findAllByType('input').filter(x=>x.props.type==='date').length,0,'Land has no depreciation start or opening');
  await renderer.act(async()=>client.setQueryData(['asset-fiscal',7],{profile:{...profile,version:2},groups,schedule:[]}));
  await renderer.act(async()=>tree.root.findByType('form').props.onSubmit({preventDefault(){}}));
  assert.equal(global.__assetFiscalSaves[0].data.expected_version,1,'Background refresh must not overwrite an edited profile version');
  assert.equal(global.__assetFiscalSaves[0].data.method,'NONE');
  assert.equal(global.__assetFiscalSaves[0].data.start_date,null);
  await renderer.act(async()=>tree.unmount());client.clear();
  const rules=await req('esbuild').build({absWorkingDir:root,entryPoints:['src/modules/finance/fixed-assets/accountRules.ts'],bundle:true,write:false,platform:'node',format:'cjs'});
  const m={exports:{}};new Function('module','exports',rules.outputFiles[0].text)(m,m.exports);
  assert.equal(m.exports.fixedAssetAccount({account_code:'100-900-100',account_type:'ASSET',normal_balance:'DEBIT'}),false,'Linen cannot enter fixed assets');
  assert.equal(m.exports.accumulatedAccountCodes['100-600-105'],'100-800-104');
  assert.equal(m.exports.accumulatedAccountCodes['100-600-999'],'100-800-999');
  console.log('PASS asset fiscal UI: method constraints, land, stale edits, linen and COA pairs');
}
run().catch(e=>{console.error(e);process.exit(1)});
