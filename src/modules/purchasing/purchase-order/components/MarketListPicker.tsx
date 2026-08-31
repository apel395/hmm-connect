import {useMemo,useState} from "react";
import Button from "@/components/ui/Button";

export interface MarketListOption {
  id:number;
  ml_number:string;
  request_date?:string;
  expiry_date?:string|null;
  status?:string;
  requester_name?:string|null;
  business_unit_id?:number|null;
  business_unit_name?:string|null;
  department_id?:number|null;
  department_name?:string|null;
  location_id?:number|null;
  location_name?:string|null;
  items?:Array<{id:number;product_name?:string;quantity?:number;remaining_quantity?:number}>;
  generated_purchase_orders?:Array<{id:number;document_number:string;status:string}>;
}

interface Props {options:MarketListOption[];selected?:MarketListOption;disabled?:boolean;onChange:(selected?:MarketListOption)=>void}

const sameOrganization=(left:MarketListOption,right:MarketListOption)=>left.business_unit_id===right.business_unit_id&&left.department_id===right.department_id&&left.location_id===right.location_id;
const itemSummary=(ml:MarketListOption)=>{const items=(ml.items??[]).filter(item=>Number(item.remaining_quantity??item.quantity??0)>0);if(!items.length)return "No remaining items";const names=items.slice(0,2).map(item=>item.product_name||"Item").join(", ");return items.length>2?`${names} +${items.length-2} more`:names};

export default function MarketListPicker({options,selected,disabled=false,onChange}:Props){
 const[open,setOpen]=useState(false);const[query,setQuery]=useState("");
 const filtered=useMemo(()=>{const needle=query.trim().toLowerCase();if(!needle)return options;return options.filter(ml=>[ml.ml_number,ml.requester_name,ml.department_name,ml.location_name,...(ml.items??[]).map(item=>item.product_name)].filter(Boolean).join(" ").toLowerCase().includes(needle))},[options,query]);
 const choose=(ml:MarketListOption)=>{if(selected?.id===ml.id){onChange(undefined);return}if(selected&&!sameOrganization(selected,ml))return;onChange(ml);setOpen(false)};
 return <div className="md:col-span-2">
   <div className="mb-1 text-sm font-medium">Approved Market List</div>
   <button type="button" disabled={disabled} onClick={()=>setOpen(true)} className="flex min-h-10 w-full items-center justify-between rounded-md border border-slate-300 bg-white px-3 py-2 text-left text-sm disabled:bg-slate-100">
     <span className={selected?"text-slate-900":"text-slate-400"}>{selected?selected.ml_number:"Search and select approved Market List..."}</span>
     <span className="ml-3 whitespace-nowrap text-xs font-semibold text-emerald-700">Browse ML</span>
   </button>
   {open&&!disabled&&<div className="fixed inset-0 z-[10001] flex items-center justify-center bg-slate-950/40 p-4" onMouseDown={event=>event.target===event.currentTarget&&setOpen(false)}>
     <div role="dialog" aria-modal="true" aria-label="Select Market List" className="flex max-h-[82vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
       <div className="flex items-center justify-between border-b px-5 py-4"><div><div className="text-lg font-semibold">Select Approved Market List</div><div className="text-xs text-slate-500">One Market List may be selected. Organization context is inherited from the source.</div></div><button type="button" className="text-2xl text-slate-500" aria-label="Close" onClick={()=>setOpen(false)}>×</button></div>
       <div className="border-b p-4"><input autoFocus value={query} onChange={event=>setQuery(event.target.value)} placeholder="Search ML number, item, requester, department, or location..." className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm"/></div>
       <div className="flex-1 overflow-auto"><table className="w-full min-w-[850px] text-sm"><thead className="sticky top-0 bg-slate-50"><tr><th className="w-12 p-3"/><th className="p-3 text-left">ML Number / Date</th><th className="p-3 text-left">Requester</th><th className="p-3 text-left">Organization</th><th className="p-3 text-left">Remaining Items</th></tr></thead><tbody>
         {filtered.map(ml=>{const incompatible=Boolean(selected&&selected.id!==ml.id&&!sameOrganization(selected,ml));const hasExistingPO=Boolean(ml.generated_purchase_orders?.length);return <tr key={ml.id} className={`border-t ${incompatible?"bg-slate-50 text-slate-400":"hover:bg-emerald-50"}`}>
           <td className="p-3 text-center"><input type="radio" checked={selected?.id===ml.id} disabled={incompatible} onChange={()=>choose(ml)} aria-label={`Select ${ml.ml_number}`}/></td>
           <td className="p-3"><div className="font-semibold">{ml.ml_number}</div><div className="text-xs text-slate-500">{ml.request_date??"—"}{ml.expiry_date?` · expires ${ml.expiry_date}`:""}</div></td>
           <td className="p-3">{ml.requester_name??"—"}</td>
           <td className="p-3"><div>{ml.location_name??"—"}</div><div className="text-xs text-slate-500">{ml.business_unit_name??"—"} · {ml.department_name??"—"}</div>{incompatible&&<div className="mt-1 text-xs text-amber-700">Different organization</div>}</td>
           <td className="p-3">{itemSummary(ml)}{hasExistingPO&&<div className="mt-1 text-xs text-slate-500">Existing PO conversion(s): {ml.generated_purchase_orders!.length}</div>}</td>
         </tr>})}
         {!filtered.length&&<tr><td colSpan={5} className="p-8 text-center text-slate-500">No matching approved Market List.</td></tr>}
       </tbody></table></div>
       <div className="flex items-center justify-between border-t px-5 py-4"><span className="text-sm text-slate-600">{selected?`${selected.ml_number} selected`:"No Market List selected"}</span><div className="flex gap-2"><Button type="button" variant="secondary" onClick={()=>onChange(undefined)}>Clear</Button><Button type="button" onClick={()=>setOpen(false)}>Use Selected ML</Button></div></div>
     </div>
   </div>}
 </div>;
}
