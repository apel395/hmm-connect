import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import Button from '@/components/ui/Button';
import SearchableSelect from '@/components/form/SearchableSelect';
import { operationsApi, type OutletContext } from '../operationsApi';
import type { CheckoutOptions, CheckoutConfiguration } from '../checkoutTypes';
const input='h-9 rounded border border-slate-300 bg-white px-2 text-sm';
export default function OutletCheckoutSettings({userId,locationId,departmentId}:{userId?:number;locationId:number;departmentId:number}){
 const scope={location_id:locationId,department_id:departmentId};
 const query=useQuery({queryKey:['pos-checkout-settings',userId,locationId,departmentId],queryFn:async()=>(await operationsApi.checkoutSettings(scope)).data,refetchOnWindowFocus:false});
 if(query.isLoading)return <p>Loading checkout settings…</p>;
 if(query.isError)return <p role="alert">Checkout settings could not load. <button className="underline" type="button" onClick={()=>void query.refetch()}>Retry</button></p>;
 return query.data?<CheckoutEditor key={`${locationId}:${departmentId}`} initial={query.data} scope={scope}/>:null;
}
function CheckoutEditor({initial,scope}:{initial:CheckoutOptions;scope:OutletContext}){
 const client=useQueryClient();
 const [config,setConfig]=useState<CheckoutConfiguration>(initial.configuration),[version,setVersion]=useState(initial.version),[busy,setBusy]=useState(false),[error,setError]=useState(''),[saved,setSaved]=useState(false);
 const invalid=config.payment_methods.some(m=>m.enabled&&!m.account_id)||config.discount_presets.some(p=>!p.name.trim()||!(Number(p.value)>0)||(p.kind==='PERCENT'&&Number(p.value)>100));
 const save=async()=>{setBusy(true);setError('');setSaved(false);try{const {data}=await operationsApi.saveCheckoutSettings(scope,config,version);setConfig(data.configuration);setVersion(data.version);setSaved(true);void client.invalidateQueries({queryKey:['pos-checkout']});void client.invalidateQueries({queryKey:['pos-checkout-settings']});}catch(e:unknown){const err=e as {response?:{data?:{detail?:string}}};setError(typeof err.response?.data?.detail==='string'?err.response.data.detail:'Could not save checkout settings');}finally{setBusy(false);}};
 return <section aria-label="Outlet checkout settings" className="space-y-4 rounded-lg border bg-white p-4">
  <h2 className="font-semibold">Discount and payment setup</h2>
  <fieldset disabled={busy} className="space-y-3"><legend className="mb-2 text-sm font-medium">Payment methods</legend>
   {config.payment_methods.map((method,index)=><div key={method.method} className="grid items-end gap-2 sm:grid-cols-[180px_1fr]"><label className="flex h-9 items-center gap-2 text-sm"><input type="checkbox" checked={method.enabled} onChange={e=>setConfig({...config,payment_methods:config.payment_methods.map((m,i)=>i===index?{...m,enabled:e.target.checked}:m)})}/>{method.method==='BANK_TRANSFER'?'Bank transfer':method.method==='CARD'?'Card':'Cash'}</label><SearchableSelect label={`${method.method} posting account`} value={method.account_id??undefined} options={initial.accounts??[]} placeholder="Choose cash, bank or clearing account" onChange={id=>setConfig({...config,payment_methods:config.payment_methods.map((m,i)=>i===index?{...m,account_id:id??null}:m)})}/></div>)}
  </fieldset>
  <fieldset disabled={busy} className="space-y-2"><legend className="mb-2 text-sm font-medium">Discount presets</legend>
   {config.discount_presets.map((preset,index)=><div key={preset.id} className="grid items-end gap-2 rounded border p-2 sm:grid-cols-[1fr_140px_130px_auto_auto]">
    <label className="text-xs">Name<input aria-label={`Discount name ${index+1}`} className={`${input} w-full`} maxLength={100} value={preset.name} onChange={e=>setConfig({...config,discount_presets:config.discount_presets.map((p,i)=>i===index?{...p,name:e.target.value}:p)})}/></label>
    <label className="text-xs">Type<select aria-label={`Discount type ${index+1}`} className={`${input} w-full`} value={preset.kind} onChange={e=>setConfig({...config,discount_presets:config.discount_presets.map((p,i)=>i===index?{...p,kind:e.target.value as 'PERCENT'|'FIXED'}:p)})}><option value="PERCENT">Percentage</option><option value="FIXED">Fixed IDR</option></select></label>
    <label className="text-xs">{preset.kind==='PERCENT'?'Percent':'Amount'}<input aria-label={`Discount value ${index+1}`} type="number" min="0.01" max={preset.kind==='PERCENT'?100:undefined} step="0.01" className={`${input} w-full`} value={preset.value} onChange={e=>setConfig({...config,discount_presets:config.discount_presets.map((p,i)=>i===index?{...p,value:e.target.value}:p)})}/></label>
    <label className="flex h-9 items-center gap-1 text-xs"><input type="checkbox" checked={preset.enabled} onChange={e=>setConfig({...config,discount_presets:config.discount_presets.map((p,i)=>i===index?{...p,enabled:e.target.checked}:p)})}/>Active</label>
    <button type="button" aria-label={`Remove discount ${index+1}`} className="h-9 text-sm text-red-700" onClick={()=>setConfig({...config,discount_presets:config.discount_presets.filter((_,i)=>i!==index)})}>Remove</button>
   </div>)}
   <Button variant="outline" size="sm" onClick={()=>setConfig({...config,discount_presets:[...config.discount_presets,{id:crypto.randomUUID(),name:'',kind:'PERCENT',value:'',enabled:true}]})}>Add discount preset</Button>
  </fieldset>
  {error&&<p role="alert" className="text-sm text-red-700">{error}</p>}{saved&&<p role="status" className="text-sm text-emerald-700">Checkout settings saved.</p>}
  <Button disabled={busy||invalid} onClick={save}>Save checkout settings</Button>
 </section>;
}
