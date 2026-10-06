/* global require, __dirname, global, EventTarget, window, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require('node:assert/strict');
const rootPath = require('node:path').resolve(__dirname, '..');
const requireProject = require('node:module').createRequire(rootPath + '/package.json');
const {build} = requireProject('esbuild');
const React = requireProject('react');
const renderer = requireProject('react-test-renderer');
global.IS_REACT_ACT_ENVIRONMENT = true;
const values = new Map();
const storage = { getItem: key => values.get(key) ?? null, setItem: (key, value) => values.set(key,value), removeItem: key => values.delete(key) };
global.window = Object.assign(new EventTarget(), {localStorage: storage});
global.__draftOwner = 45;
async function run() {
 const bundle = await build({absWorkingDir:rootPath,tsconfig:rootPath+'/tsconfig.app.json',entryPoints:['src/hooks/useFormRecovery.ts'],bundle:true,write:false,platform:'node',format:'cjs',external:['react'],plugins:[{name:'services',setup(build){build.onResolve({filter:/^(@\/store\/auth|sonner)$/},args=>({path:args.path,namespace:'mock'}));build.onLoad({filter:/.*/,namespace:'mock'},args=>({contents:args.path==='sonner'?'export const toast={success(){}};':'export default selector => selector({user:{id:globalThis.__draftOwner}});'}));}}]});
 const module={exports:{}}; new Function('module','exports','require',bundle.outputFiles[0].text)(module,module.exports,name=>name==='react'?React:requireProject(name));
 const useRecovery=module.exports.default;
 const valid=x=>!!x&&typeof x.description==='string';
 const input={description:'Typed before accidental close',lines:[{account_id:215,debit:5500000,credit:0}]};
 let recovery;
 function Form({value,active,name='journal:create'}) { recovery=useRecovery(name,value,active,valid); return null; }
 let view;
 await renderer.act(async()=>{view=renderer.create(React.createElement(Form,{value:input,active:true}));});
 assert.equal(values.size,1);
 await renderer.act(async()=>{view.update(React.createElement(Form,{value:input,active:false}));});
 await renderer.act(async()=>view.unmount());
 await renderer.act(async()=>{view=renderer.create(React.createElement(Form,{value:{description:''},active:false}));});
 assert.deepEqual(recovery.load(),input);
 await renderer.act(async()=>{view.update(React.createElement(Form,{value:input,active:true}));});
 await renderer.act(async()=>{recovery.clear();view.update(React.createElement(Form,{value:{description:''},active:false}));});
 await renderer.act(async()=>view.unmount());
 assert.equal(values.size,0,'cleared recovery must not return on unmount');
 await renderer.act(async()=>{view=renderer.create(React.createElement(Form,{value:input,active:true,name:'journal:edit:1'}));});
 global.__draftOwner=46;
 await renderer.act(async()=>view.update(React.createElement(Form,{value:input,active:true,name:'journal:edit:1'})));
 assert.equal([...values.keys()].some(k=>k.includes(':46:')),false,'owner change must never copy old input');
 assert.equal(recovery.load(),null);
 await renderer.act(async()=>view.unmount());
 global.__draftOwner=47;
 Object.defineProperty(window,'localStorage',{configurable:true,get(){throw new Error('Storage denied');}});
 await renderer.act(async()=>{view=renderer.create(React.createElement(Form,{value:input,active:true}));});
 assert.equal(recovery.failed,true);
 await renderer.act(async()=>view.update(React.createElement(Form,{value:input,active:false})));
 assert.deepEqual(recovery.load(),input,'same-session memory recovery survives storage denial');
 await renderer.act(async()=>{recovery.clear();view.unmount();});
 console.log('React hook lifecycle PASS: close/reopen, remount, clear without resurrection, user isolation and denied-storage memory fallback.');
}
run().catch(error=>{console.error(error);process.exitCode=1;});
