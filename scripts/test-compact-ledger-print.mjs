import assert from 'node:assert/strict';
import path from 'node:path';
import {createRequire} from 'node:module';
import {build} from 'esbuild';
import {createElement} from 'react';
import {renderToStaticMarkup} from 'react-dom/server';
const require=createRequire(import.meta.url);
async function compile(entry){
 const r=await build({entryPoints:[entry],alias:{'@':path.resolve('src')},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime'],plugins:[{name:'api',setup(b){b.onResolve({filter:/^@\/api\/client$/},a=>({path:a.path,namespace:'mock'}));b.onLoad({filter:/.*/,namespace:'mock'},()=>({contents:'export default {};',loader:'js'}));}}]});
 const m={exports:{}};new Function('module','exports','require',r.outputFiles[0].text)(m,m.exports,require);return m.exports;
}
const {matchingSelectOptions}=await compile('src/components/form/searchableSelectOptions.ts');
const options=Array.from({length:175},(_,i)=>({id:i+1,label:`700-500-${i} — Account ${i}${i===174?' (Inactive)':''}`}));
assert.equal(matchingSelectOptions(options,'',Infinity).length,175);
assert.equal(matchingSelectOptions(options,'Account 174',Infinity)[0].id,175);
assert.equal(matchingSelectOptions(options,'inactive',Infinity)[0].id,175);
assert.equal(matchingSelectOptions(options,'',50).length,50);
const {default:Template}=await compile('src/components/print/DocumentPrintTemplate.tsx');
const html=renderToStaticMarkup(createElement(Template,{title:'Purchase Order',documentNumber:'PO-TEST',columns:[],rows:[],signatures:[{label:'Created by',name:'Creator A',signedAt:'2026-10-14T03:00:00Z'},{label:'Approver 1',name:'Approver A',signedAt:'2026-10-14T04:00:00Z'},{label:'Approver 2',name:'Approver B',signedAt:'2026-10-14T05:00:00Z'}]}));
assert.doesNotMatch(html,/DOCUMENT AUTHENTICITY|Print #1/);
for(const text of ['Creator A','Approver A','Approver B','10.00 WIB','11.00 WIB','12.00 WIB'])assert.ok(html.includes(text),text);
assert.equal((html.match(/Signature space/g)||[]).length,3);
console.log('PASS: all 175 accounts including inactive/end-of-list searchable; recorded WIB times, separate signatures and preview without print count.');
