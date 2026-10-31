/* global EventTarget, Event, window */
import assert from 'node:assert/strict';
import console from 'node:console';
import path from 'node:path';
import { createRequire } from 'node:module';
import { build } from 'esbuild';
const require=createRequire(import.meta.url);
const React=require('react'),renderer=require('react-test-renderer');
globalThis.IS_REACT_ACT_ENVIRONMENT=true;
async function compile(entry){
 const result=await build({entryPoints:[entry],alias:{'@':path.resolve('src')},bundle:true,write:false,platform:'node',format:'cjs',jsx:'automatic',external:['react','react/jsx-runtime','react-dom'],plugins:[{name:'print-tests',setup(b){
  b.onResolve({filter:/^@\/api\/client$/},()=>({path:'api',namespace:'fake'}));
  b.onResolve({filter:/^\.\/documentPdf$/},()=>({path:'pdf',namespace:'fake'}));
  b.onResolve({filter:/^sonner$/},()=>({path:'toast',namespace:'fake'}));
  b.onLoad({filter:/.*/,namespace:'fake'},a=>({loader:'js',contents:a.path==='api'?'export default {post:(url,body)=>globalThis.__printPost(url,body)};':a.path==='pdf'?'export async function downloadDocumentPdf(){globalThis.__pdfCalls++;}':'export const toast={error:()=>{globalThis.__printErrors++;}};'}));
 }}]});
 const mod={exports:{}};new Function('module','exports','require',result.outputFiles[0].text)(mod,mod.exports,require);return mod.exports;
}
const {createPrintSession,attachNativePrintTracking,printSnapshot}=await compile('src/components/print/printTracking.ts');
assert.equal((await printSnapshot('snapshot')).length,64);
let calls=[],fail=true;
globalThis.__printPost=async(url,body)=>{calls.push({url,body});if(fail){fail=false;throw Error('Lost response');}return{data:{print_count:1}};};
const retry=createPrintSession({kind:'PURCHASE_ORDER',id:1,revision:'a'.repeat(64)});
await assert.rejects(retry.issue('PRINT_DIALOG'));
await retry.issue('PRINT_DIALOG');assert.equal(calls[0].body.request_id,calls[1].body.request_id,'retry keeps request ID');
await retry.issue('PRINT_DIALOG');assert.notEqual(calls[1].body.request_id,calls[2].body.request_id,'new attempt gets new ID');
let release;globalThis.__printPost=()=>new Promise(resolve=>{release=resolve;});
const flight=createPrintSession({kind:'MARKET_LIST',id:1});const first=flight.issue('PRINT_DIALOG'),second=flight.issue('PRINT_DIALOG');assert.equal(first,second);release({data:{print_count:1}});await first;

const makeWindow=()=>{const target=new EventTarget();target.location={pathname:'/purchase-orders/1/print'};target.print=()=>{target.dispatchEvent(new Event('beforeprint'));target.dispatchEvent(new Event('afterprint'));};return target;};
const target=makeWindow();let nativeCount=0;
const native=attachNativePrintTracking(target,async()=>{nativeCount++;},()=>assert.fail('unexpected print error'));
native.prepared();target.print();await Promise.resolve();assert.equal(nativeCount,0,'prepared application print is not counted again by beforeprint');
target.dispatchEvent(new Event('beforeprint'));target.dispatchEvent(new Event('beforeprint'));await Promise.resolve();assert.equal(nativeCount,1,'duplicate beforeprint is one attempt');
target.dispatchEvent(new Event('afterprint'));assert.equal(nativeCount,1,'cancel/afterprint never records successful physical output');
const key=new Event('keydown',{cancelable:true});Object.assign(key,{ctrlKey:true,key:'p'});target.dispatchEvent(key);await new Promise(resolve=>setTimeout(resolve,0));assert.ok(key.defaultPrevented);assert.equal(nativeCount,2);
native.dispose();target.print();assert.equal(nativeCount,2,'unmount removes listeners');

const {default:Template}=await compile('src/components/print/DocumentPrintTemplate.tsx');
const text=node=>node.children.map(child=>typeof child==='string'?child:text(child)).join('');
for(const kind of ['PURCHASE_REQUISITION','MARKET_LIST','PURCHASE_ORDER','GOODS_RECEIPT']){
 globalThis.window=makeWindow();globalThis.__pdfCalls=0;globalThis.__printErrors=0;
 let prints=0,pdfs=0;calls=[];
 globalThis.__printPost=async(url,body)=>{calls.push({url,body});if(body.action==='PRINT_DIALOG')prints++;else pdfs++;return{data:{print_count:prints,pdf_download_count:pdfs,channel:body.action,revision_number:1,reprint_number:Math.max(0,prints-1),actor_name:'Operator',requested_at:'2026-10-30T01:00:00Z',physical_print_confirmed:false}};};
 let view;
 await renderer.act(async()=>{view=renderer.create(React.createElement(Template,{title:'Purchasing document',documentNumber:'TEST-1',printTarget:{kind,id:1,revision:'a'.repeat(64)},columns:[{label:'Code',render:()=> 'A'}],rows:[{}]}),{createNodeMock:element=>element.type==='article'?{}:null});});
 assert.equal(calls.length,0,'opening preview does not count');
 await renderer.act(async()=>{await view.root.findByProps({'aria-label':'Print document'}).props.onClick();});
 assert.equal(prints,1);assert.equal(calls.length,1);assert.equal(calls[0].body.expected_revision,'a'.repeat(64));assert.ok(calls[0].url.includes(kind));assert.ok(text(view.root).includes('Print attempt #1'));
 const button=view.root.findAllByType('button').find(button=>text(button)==='Download PDF');
 await renderer.act(async()=>{await button.props.onClick();});
 assert.equal(pdfs,1);assert.equal(prints,1);assert.equal(globalThis.__pdfCalls,1);assert.ok(text(view.root).includes('PDF download #1'));
 const count=calls.length;await renderer.act(async()=>view.unmount());window.print();assert.equal(calls.length,count);
}
console.log('Purchasing print tracking PASS: no preview count, stable retries, in-flight deduplication, native/cancel handling, PR/ML/PO/RR print attempts, separate PDF downloads and listener cleanup.');
