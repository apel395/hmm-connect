/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');
global.IS_REACT_ACT_ENVIRONMENT=true;
async function run(){
 const {build}=req('esbuild');
 const result=await build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/master/products/components/ItemNumberInput.tsx'],bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime']});
 const mod={exports:{}};new Function('module','exports','require',result.outputFiles[0].text)(mod,mod.exports,req);
 let view,actual,setExternal;
 function Harness(){const [value,setValue]=React.useState(0);actual=value;setExternal=setValue;return React.createElement(mod.exports.default,{value,min:0,step:'0.01',onChange:e=>setValue(Number(e.target.value))});}
 await renderer.act(async()=>{view=renderer.create(React.createElement(Harness));});
 const field=()=>view.root.findByType('input');
 async function enter(value){const node={value};await renderer.act(async()=>field().props.onChange({target:node,currentTarget:node}));}
 assert.equal(field().props.value,'','Zero is a placeholder, not a forced editable prefix');
 await enter('010');assert.equal(field().props.value,'10');assert.equal(actual,10);
 await enter('00025000');assert.equal(field().props.value,'25000');assert.equal(actual,25000);
 await enter('0.50');assert.equal(field().props.value,'0.50');assert.equal(actual,.5);
 await enter('000.75');assert.equal(field().props.value,'0.75');assert.equal(actual,.75);
 await enter('');assert.equal(field().props.value,'');assert.equal(actual,0);
 await enter('0');await renderer.act(async()=>field().props.onFocus({currentTarget:{value:'0'}}));assert.equal(field().props.value,'');
 await enter('00230000.50');assert.equal(field().props.value,'230000.50');assert.equal(actual,230000.5);
 await renderer.act(async()=>setExternal(123.45));assert.equal(field().props.value,'123.45');
 await renderer.act(async()=>setExternal(0));assert.equal(field().props.value,'');
 assert.equal(field().props.min,0);assert.equal(field().props.step,'0.01');
 await renderer.act(async()=>view.unmount());
 console.log('Item numeric fields: blank zero, leading-zero removal, decimal preservation, deletion and external updates passed.');
}
run().catch(e=>{console.error(e);process.exit(1);});
