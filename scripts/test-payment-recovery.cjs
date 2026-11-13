/* global require, __dirname, global, console, process, EventTarget, setTimeout */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require('node:assert/strict');
const root = require('node:path').resolve(__dirname, '..');
const req = require('node:module').createRequire(root + '/package.json');
const React = req('react');
const renderer = req('react-test-renderer');
const {QueryClient, QueryClientProvider} = req('@tanstack/react-query');
global.IS_REACT_ACT_ENVIRONMENT = true;
const values = new Map();
global.window = Object.assign(new EventTarget(), {localStorage:{getItem:k=>values.get(k)??null,setItem:(k,v)=>{values.set(k,v);},removeItem:k=>{values.delete(k);}}});
const route = {pathname:'/accounts-payable/payments',search:'',state:null};
let resolveInvoices, rejectInvoices, invoiceResponse, savedCalls, errors, lastPayload, createFailure, navigations;
const saved = {supplier_id:22,payment_date:'2026-10-28',payment_method:'BANK_TRANSFER',currency:'IDR',reference_number:'KEEP-REFERENCE',notes:'Keep my notes',allocations:[{supplier_invoice_id:802,allocated_amount:100}],funding_lines:[{bank_account_id:9,amount:100}]};
const deferred = () => new Promise((resolve,reject)=>{resolveInvoices=resolve;rejectInvoices=reject;});
let pending;
global.__paymentMocks = {
 route, owner:45,
 toast:{success(){},error(message){errors.push(message);}},
 navigate(path){navigations.push(path);},
 listPayments:async()=>({items:[]}),listReadyToPay:async()=>({items:[],totals_by_currency:{}}),
 eligibleSuppliers:async()=>[{id:22,code:'S22',name:'Supplier'},{id:259,code:'S259',name:'Historic Supplier'}],
 eligibleInvoices:()=>pending,
 eligibleVouchers:async()=>[],
 listBankAccounts:async()=>[{id:9,currency:'IDR',bank_name:'Bank',account_name:'Cash',account_number:'99'},{id:61,currency:'IDR',bank_name:'Bank',account_name:'Checking',account_number:'61'}],
 listLocations:async()=>[],getAllAccountLookup:async()=>[],
 createPayment:async(payload)=>{savedCalls++;lastPayload=payload;if(createFailure)throw createFailure;return {id:1};},updatePayment:async(payload)=>{savedCalls++;return {id:7};},paymentAction:async()=>{},
 getPayment:async()=>({...saved,id:7,total_amount:100,allocations:[{supplier_invoice_id:802,allocated_amount:100,current_available_balance:100,invoice_number:'INV-802'}]})
};
async function main(){
 const bundle=await req('esbuild').build({absWorkingDir:root,tsconfig:root+'/tsconfig.app.json',entryPoints:['src/modules/finance/payments/PaymentListPage.tsx'],bundle:true,write:false,platform:'node',format:'cjs',external:['react','@tanstack/react-query'],plugins:[{name:'mocks',setup(build){
 build.onResolve({filter:/^(sonner|react-router-dom|lucide-react|@\/store\/auth|@\/hooks\/useAuthorization|@\/components\/|@\/modules\/master\/chart-of-accounts\/api|@\/modules\/finance\/cash-flow\/bankAccountApi|@\/modules\/admin\/organization\/api)/},args=>({path:args.path,namespace:'mock'}));
 build.onResolve({filter:/^\.\/api$/},args=>args.importer.endsWith('PaymentListPage.tsx')?{path:'payment-api',namespace:'mock'}:undefined);
 build.onLoad({filter:/.*/,namespace:'mock'},args=>{
 const m='const m=globalThis.__paymentMocks;';let code;
 if(args.path==='sonner') code=m+'export const toast=m.toast;';
 else if(args.path==='react-router-dom') code=m+'export const useNavigate=()=>m.navigate,useLocation=()=>m.route;export const Link=({children})=>children;';
 else if(args.path==='lucide-react') code='export const Printer=()=>null,SlidersHorizontal=()=>null;';
 else if(args.path==='@/store/auth') code=m+'export default selector=>selector({user:{id:m.owner}});';
 else if(args.path==='@/hooks/useAuthorization') code='export default ()=>({hasPermission:()=>true,isSuperuser:()=>true});';
 else if(args.path==='payment-api') code=m+'export const {createPayment,eligibleInvoices,eligibleSuppliers,eligibleVouchers,getPayment,listPayments,listReadyToPay,paymentAction,updatePayment}=m;';
 else if(args.path.includes('chart-of-accounts')) code=m+'export const getAllAccountLookup=m.getAllAccountLookup;';
 else if(args.path.includes('bankAccountApi')) code=m+'export const listBankAccounts=m.listBankAccounts;';
 else if(args.path.includes('organization/api')) code=m+'export const listLocations=m.listLocations;';
 else {
 code='import React from "react";const Wrap=({children})=>React.createElement("div",null,children);';
 if(args.path.endsWith('PageHeader')) code+='export default ({actions})=>React.createElement("header",null,actions);';
 else if(args.path.endsWith('/Button')) code+='export default ({children,...props})=>React.createElement("button",props,children);';
 else if(args.path.endsWith('/Dialog')) code+='export default ({open,children})=>open?React.createElement(Wrap,null,children):null;export const DialogBody=Wrap,DialogContent=Wrap,DialogFooter=Wrap,DialogHeader=Wrap,DialogTitle=Wrap;';
 else if(args.path.endsWith('/Table')) code+='export const Table=Wrap,TBody=Wrap,TD=Wrap,TH=Wrap,THead=Wrap,TR=Wrap,TableCellStack=Wrap;';
 else if(args.path.endsWith('SearchableSelect')) code+='export default ({label,value,onChange})=>React.createElement("input",{"aria-label":label,value:value??"",onChange:e=>onChange(Number(e.target.value))});';
 else if(args.path.endsWith('CurrencyInput')) code+='export default ({value,onValueChange})=>React.createElement("input",{value,onChange:e=>onValueChange(Number(e.target.value))});';
 else code+='export default Wrap;';
 }
 return {contents:code};});}}]});
 const module={exports:{}};new Function('module','exports','require',bundle.outputFiles[0].text)(module,module.exports,req);
 const Page=module.exports.default;
 const flush=()=>new Promise(resolve=>setTimeout(resolve,15));
 const buttons=(view,label)=>view.root.findAllByType('button').filter(b=>b.children.join('')===label);
 const text=view=>JSON.stringify(view.toJSON());
 async function mount({restore=true,edit=false,draft=saved}={}){
 values.clear();global.__paymentMocks.owner++;errors=[];savedCalls=0;lastPayload=null;createFailure=null;navigations=[];pending=deferred();invoiceResponse=[{id:802,invoice_number:'INV-802',available_balance:100,total_amount:100}];
 route.search=edit?'?edit=7':'';
 if(restore)values.set(`hmm-form-input:v1:${global.__paymentMocks.owner}:payment%3A${edit?'edit%3A7':'create'}`,JSON.stringify({version:1,value:draft}));
 const qc=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:0},mutations:{retry:false}}});let view;
 await renderer.act(async()=>{view=renderer.create(React.createElement(QueryClientProvider,{client:qc},React.createElement(Page)));await flush();});
 await renderer.act(async()=>{await flush();});
 if(!edit) await renderer.act(async()=>{buttons(view,'Create Payment')[0].props.onClick();await flush();});
 return {view,qc};
 }
 async function dispose({view,qc}){await renderer.act(async()=>{view.unmount();qc.clear();});}
 let context=await mount({restore:false});assert.ok(buttons(context.view,'Save Draft').length);await dispose(context);
 context=await mount();
 assert.match(text(context.view),/Refreshing invoice balances/);
 assert.equal(buttons(context.view,'Save Draft')[0].props.disabled,true);
 assert.match(text(context.view),/KEEP-REFERENCE/);
 await renderer.act(async()=>{resolveInvoices(invoiceResponse);await flush();});
 assert.doesNotMatch(text(context.view),/Unavailable invoice selections/);
 assert.match(text(context.view),/INV-802/);
 assert.match(text(context.view),/Keep my notes/);
 assert.equal(buttons(context.view,'Save Draft')[0].props.disabled,false);
 // Save must recheck the server even when the visible cached balance allows it.
 pending=Promise.resolve([{...invoiceResponse[0],available_balance:50}]);
 await renderer.act(async()=>{buttons(context.view,'Save Draft')[0].props.onClick();await flush();});
 assert.equal(savedCalls,0);assert.match(errors.at(-1),/no longer available for this amount/);
 // Refetch can invalidate a selection; never reuse the restored balance.
 pending=Promise.resolve([]);
 await renderer.act(async()=>{await context.qc.invalidateQueries({queryKey:['eligible-payment-invoices']});await flush();});
 assert.match(text(context.view),/Unavailable invoice selections/);
 assert.match(text(context.view),/#802/);
 await renderer.act(async()=>buttons(context.view,'Save Draft')[0].props.onClick());
 assert.equal(savedCalls,0);assert.match(errors.at(-1),/Remove unavailable/);
 await renderer.act(async()=>context.view.root.findByProps({'aria-label':'Remove unavailable invoice 802'}).props.onClick());
 assert.doesNotMatch(text(context.view),/Unavailable invoice selections/);
 assert.match(text(context.view),/KEEP-REFERENCE/);await dispose(context);
 context=await mount();
 await renderer.act(async()=>{rejectInvoices(new Error('Network offline'));await flush();});
 assert.match(text(context.view),/Your input is preserved/);
 assert.ok(buttons(context.view,'Retry invoice loading').length);
 await renderer.act(async()=>buttons(context.view,'Save Draft')[0].props.onClick());
 assert.equal(savedCalls,0);assert.match(errors.at(-1),/could not be loaded/);
 pending=Promise.resolve(invoiceResponse);
 await renderer.act(async()=>{buttons(context.view,'Retry invoice loading')[0].props.onClick();await flush();});
 assert.match(text(context.view),/INV-802/);
 await renderer.act(async()=>{buttons(context.view,'Save Draft')[0].props.onClick();await flush();});
 assert.equal(savedCalls,1,'a valid restored selection can still be saved');await dispose(context);
 context=await mount({edit:true});
 assert.match(text(context.view),/Edit Draft Supplier Payment/);
 await renderer.act(async()=>{resolveInvoices([]);await flush();});
 assert.match(text(context.view),/Unavailable invoice selections/);
 await renderer.act(async()=>buttons(context.view,'Save Changes')[0].props.onClick());
 assert.equal(savedCalls,0);await dispose(context);
 // Production incident: JavaScript floats must be serialized as exact monetary cents.
 const floatingDraft = {
   ...saved,supplier_id:259,payment_date:'2026-02-06',
   total_amount:950999.8400000001,bank_charge_amount:0,short_over_amount:0.16,
   short_over_account_id:82,difference_reason:'pembulatan',
   allocations:[{supplier_invoice_id:733,allocated_amount:497999.84},{supplier_invoice_id:732,allocated_amount:453000}],
   funding_lines:[{bank_account_id:61,amount:951000.0000000001}],
 };
 const liveInvoiceRows = [
   {id:733,invoice_number:'INV-733',available_balance:497999.84,total_amount:497999.84},
   {id:732,invoice_number:'INV-732',available_balance:453000,total_amount:453000},
 ];
 context = await mount({draft:floatingDraft});
 await renderer.act(async()=>{resolveInvoices(liveInvoiceRows);await flush();});
 assert.equal(buttons(context.view,'Save Draft')[0].props.disabled,false);
 // Mock FastAPI validation detail as an object array: never send React object children into Sonner.
 createFailure = {response:{status:422,data:{detail:[{type:'value_error',loc:['body'],msg:'Value error, Invoice allocations must equal payment total'}]}}};
 pending = Promise.resolve(liveInvoiceRows);
 await renderer.act(async()=>{buttons(context.view,'Save Draft')[0].props.onClick();await flush();});
 assert.equal(savedCalls,1);
 assert.equal(typeof errors.at(-1),'string','422 detail objects must be converted to text');
 assert.match(errors.at(-1),/Invoice allocations must equal payment total/);
 assert.ok(buttons(context.view,'Save Draft').length,'validation error must not close the form');
 assert.equal(lastPayload.total_amount,950999.84);
 assert.equal(lastPayload.short_over_amount,0.16);
 assert.equal(lastPayload.funding_lines[0].amount,951000);
 assert.deepEqual(lastPayload.allocations.map(row=>row.allocated_amount),[497999.84,453000]);
 assert.deepEqual(navigations,[],'a failed save must not navigate');
 createFailure = null;
 await renderer.act(async()=>{buttons(context.view,'Save Draft')[0].props.onClick();await flush();});
 assert.equal(savedCalls,2);
 assert.ok(navigations.includes('/payments/1'),'successful retry must navigate to saved payment');
 await dispose(context);

 console.log('Payment recovery PASS: invalid invoice recovery, edit draft, 422 toast safety, integer-cent payment totals and successful retry.');
}
main().catch(error=>{console.error(error);process.exitCode=1;});
