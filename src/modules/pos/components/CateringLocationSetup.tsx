import { useState } from "react";
import SearchableSelect from "@/components/form/SearchableSelect";
import Button from "@/components/ui/Button";
import CateringBillingFields from "./CateringBillingFields";
import { posApi } from "../api";
import type { CateringProfile, Choice } from "../cateringTypes";
const input="h-9 w-full rounded border px-2 text-sm";
export default function CateringLocationSetup({locationId,profile,customers,departments,revenueAccounts,receivableAccounts,onSaved,onClose}:{locationId:number;profile:CateringProfile;customers:Choice[];departments:Choice[];revenueAccounts:Choice[];receivableAccounts:Choice[];onSaved:()=>void;onClose:()=>void}) {
  const [value,setValue]=useState(()=>profile.configuration);
  const [busy,setBusy]=useState(false),[error,setError]=useState("");
  const [search,setSearch]=useState("");
  const choices=profile.service_choices.filter(p=>`${p.code||''} ${p.name}`.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
  const save=async()=>{setBusy(true);setError("");try{await posApi.saveCateringSettings(locationId,value);onSaved();}catch(e:unknown){const err=e as {response?:{data?:{detail?:string}}};setError(typeof err.response?.data?.detail==='string'?err.response.data.detail:'Could not save location settings');}finally{setBusy(false);}};
  return <section aria-label="Catering location billing settings" className="space-y-3 rounded-lg border bg-slate-50 p-4">
    <div className="flex items-center justify-between"><h2 className="font-semibold">Location billing defaults</h2><button type="button" onClick={onClose} disabled={busy}>Close</button></div>
    <fieldset disabled={busy} className="grid gap-3 md:grid-cols-3">
      <SearchableSelect label="Default customer" value={value.customer_id??undefined} options={customers} onChange={id=>setValue({...value,customer_id:id??null})}/>
      <SearchableSelect label="Default department" value={value.department_id??undefined} options={departments} onChange={id=>setValue({...value,department_id:id??null})}/>
      <label className="text-xs">Payment terms (days)<input className={input} type="number" min={0} max={365} value={value.payment_term_days??''} onChange={e=>setValue({...value,payment_term_days:e.target.value===''?null:Number(e.target.value)})}/></label>
      <SearchableSelect label="Default revenue account" value={value.revenue_account_id??undefined} options={revenueAccounts} onChange={id=>setValue({...value,revenue_account_id:id??null})}/>
      <SearchableSelect label="Default receivable account" value={value.receivable_account_id??undefined} options={receivableAccounts} onChange={id=>setValue({...value,receivable_account_id:id??null})}/>
    </fieldset>
    <CateringBillingFields disabled={busy} value={value.billing} onChange={billing=>setValue({...value,billing})}/>
    <fieldset disabled={busy} className="space-y-2"><legend className="text-sm font-medium">Additional services available at this location</legend>
      <input aria-label="Search shared services" placeholder="Search service code or name" className={input} value={search} onChange={e=>setSearch(e.target.value)}/>
      <div className="grid max-h-44 gap-2 overflow-auto rounded border bg-white p-2 md:grid-cols-2">{choices.map(p=><label className="flex items-start gap-2 text-xs" key={p.id}><input type="checkbox" checked={value.service_product_ids.includes(p.id)} onChange={e=>setValue({...value,service_product_ids:e.target.checked?[...value.service_product_ids,p.id]:value.service_product_ids.filter(id=>id!==p.id)})}/>{p.code} — {p.name}</label>)}</div>
    </fieldset>
    {error&&<p role="alert" className="text-sm text-red-700">{error}</p>}
    <Button disabled={busy} onClick={save}>Save location defaults</Button>
  </section>;
}
