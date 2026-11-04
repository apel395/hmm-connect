import type { BillingDetails } from "../cateringTypes";
const input="h-9 w-full rounded-md border border-slate-300 bg-white px-2 text-sm";
export default function CateringBillingFields({value,onChange,disabled=false}:{value:BillingDetails;onChange:(v:BillingDetails)=>void;disabled?:boolean}) {
  return <fieldset disabled={disabled} className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
    {([['billing_name','Bill to'],['attention','Attention'],['contract_number','Contract number']] as const).map(([key,label])=><label key={key} className="text-xs">{label}<input className={input} maxLength={key==='contract_number'?100:200} value={value[key]} onChange={e=>onChange({...value,[key]:e.target.value})}/></label>)}
    <label className="text-xs">Contract date<input type="date" className={input} value={value.contract_date||""} onChange={e=>onChange({...value,contract_date:e.target.value||null})}/></label>
    <label className="text-xs">Invoice layout<select className={input} value={value.template} onChange={e=>onChange({...value,template:e.target.value as BillingDetails['template']})}><option value="phr">Catering service invoice</option><option value="standard">Standard invoice</option></select></label>
    <label className="text-xs">Billing address<textarea className={`${input} !h-16 py-1`} maxLength={1000} value={value.billing_address} onChange={e=>onChange({...value,billing_address:e.target.value})}/></label>
    <label className="text-xs sm:col-span-2">Payment instructions<textarea className={`${input} !h-16 py-1`} maxLength={2000} value={value.payment_instructions} onChange={e=>onChange({...value,payment_instructions:e.target.value})}/></label>
  </fieldset>;
}
