/* global require, __dirname, global, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert=require('node:assert/strict'),root=require('node:path').resolve(__dirname,'..'),req=require('node:module').createRequire(root+'/package.json');
const React=req('react'),renderer=req('react-test-renderer');global.IS_REACT_ACT_ENVIRONMENT=true;
global.__receipt={id:10,receipt_number:'GR-POSTED',status:'POSTED',source_type:'HISTORICAL_ENTRY',items:[],supplier_invoice_id:650,supplier_invoice_status:'DRAFT',allowed_actions:{can_edit:false,edit_block_reason:'This receiving is posted. Use the correction or return workflow.',can_post:false,can_return:false,can_correct_cost:false,can_print:false,can_manage_attachments:false,can_view_history:false}};
async function run(){
 const bundled=await req('esbuild').build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/purchasing/goods-receipts/pages/ReceivingDetailPage.tsx'],bundle:true,write:false,platform:'node',format:'cjs',external:['react','react/jsx-runtime'],plugins:[{name:'mocks',setup(b){
 b.onResolve({filter:/^(?:@\/components\/|@\/modules\/|@\/hooks\/|@tanstack\/react-query|sonner|lucide-react|react-router-dom|\.\.\/hooks\/useGoodsReceipts|\.\.\/components\/EditReceivingDialog|\.\.\/\.\.\/components\/DocumentActivity)/},a=>({path:a.path,namespace:'mock'}));
 b.onLoad({filter:/.*/,namespace:'mock'},a=>{let contents;
 if(a.path==='sonner')contents='export const toast={error:()=>{},success:()=>{}};';
 else if(a.path==='lucide-react')contents='export const FileCheck2=()=>null,FilePlus2=()=>null,Pencil=()=>null,PencilLine=()=>null,RotateCcw=()=>null;';
 else if(a.path.includes('useGoodsReceipts'))contents='export const useGoodsReceipt=()=>({data:globalThis.__receipt,isLoading:false});const action=()=>({isPending:false,mutate(){}});export const useApproveGoodsReceipt=action,useCorrectGoodsReceiptCosts=action,usePostGoodsReceipt=action,useRejectGoodsReceipt=action,useReturnGoodsReceipt=action,useSubmitGoodsReceipt=action;';
 else if(a.path.includes('useAuthorization'))contents='export default ()=>({hasPermission:()=>true,isSuperuser:()=>true,canPerform:()=>false});';
 else if(a.path==='@tanstack/react-query')contents='export const useQueryClient=()=>({invalidateQueries:()=>{}});export const useMutation=()=>({isPending:false});';
 else if(a.path.includes('supplier-invoices/api'))contents='export const prepareInvoiceFromReceipt=async()=>({});';
 else if(a.path==='react-router-dom')contents="import React from 'react';export const useParams=()=>({id:'10'});export const useNavigate=()=>()=>{};export const Link=p=>React.createElement('a',{href:p.to},p.children);";
 else if(a.path.endsWith('/Dialog'))contents="import React from 'react';export const DialogBody=p=>React.createElement('div',null,p.children);export const DialogContent=DialogBody,DialogFooter=DialogBody,DialogHeader=DialogBody,DialogTitle=DialogBody;export default p=>p.open?React.createElement('div',null,p.children):null;";
 else if(a.path.endsWith('/Button'))contents="import React from 'react';export default p=>React.createElement('button',p,p.children);";
 else contents="import React from 'react';export default p=>React.createElement('div',null,p.children);";
 return {contents,loader:'js'};});}}]});
 const m={exports:{}};new Function('module','exports','require',bundled.outputFiles[0].text)(m,m.exports,n=>req(n));let v;await renderer.act(async()=>{v=renderer.create(React.createElement(m.exports.default));});const text=n=>n.children.map(c=>typeof c==='string'?c:text(c)).join('');
 const edit=v.root.findAllByType('button').find(n=>text(n).trim()==='Edit Receiving');assert.ok(edit,'Edit remains discoverable after invoice creation and posting');await renderer.act(async()=>edit.props.onClick());assert.ok(text(v.root).includes('This receiving is posted.'));assert.ok(v.root.findAllByType('a').some(n=>n.props.href==='/supplier-invoices/650'),'correction explanation links to source invoice');assert.ok(!text(v.root).includes('Save Changes'),'posted receipt never opens mutable draft form');await renderer.act(async()=>v.unmount());
 console.log('Receiving action PASS: posted Edit button remains visible, explains restrictions and links invoice without exposing draft save.');
}
run().catch(e=>{console.error(e);process.exitCode=1;});
