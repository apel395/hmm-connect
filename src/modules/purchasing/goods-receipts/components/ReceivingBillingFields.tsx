import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import CurrencyInput from "@/components/form/CurrencyInput";
import SearchableSelect from "@/components/form/SearchableSelect";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { billingTotal, type ReceivingBilling } from "../billing";

type Props = { value: ReceivingBilling; onChange: (next: ReceivingBilling) => void; subtotal: number; tax: number; open?: boolean };
const money = (v: number) => v.toLocaleString("id-ID", {minimumFractionDigits:2,maximumFractionDigits:2});
export default function ReceivingBillingFields({value, onChange, subtotal, tax, open = true}: Props) {
  const accounts = useQuery({queryKey:["receiving-billing-expense-accounts"],
    queryFn:()=>getAllAccountLookup({account_type:"EXPENSE",is_active:true,is_posting:true}),enabled:open});
  const mapping = useQuery({queryKey:["receiving-charge-accounts"],
    queryFn:async()=>(await api.get("/goods-receipts/charge-accounts")).data,enabled:open});
  const update = <K extends keyof ReceivingBilling>(key:K,next:ReceivingBilling[K]) => onChange({...value,[key]:next});
  const options=(accounts.data??[]).filter((a:any)=>a.normal_balance==="DEBIT").map((a:any)=>({id:Number(a.id),label:`${a.account_code} — ${a.account_name}`,keywords:[a.account_code,a.account_name]}));
  const discount=mapping.data?.discount_account;
  return <section className="space-y-2 border-t pt-3">
    <div className="grid gap-3 md:grid-cols-3">
      {(["admin","shipping"] as const).map(kind=><div key={kind} className="space-y-1">
        <label className="text-xs font-medium">{kind==="admin"?"Additional charges":"Shipping cost"}<CurrencyInput value={value[`${kind}_fee_amount`]} onValueChange={v=>update(`${kind}_fee_amount`,v)}/></label>
        <SearchableSelect aria-label={`${kind} expense account`} value={value[`${kind}_fee_account_id`]??undefined} placeholder="Choose expense account" options={options} disabled={accounts.isLoading} onChange={id=>update(`${kind}_fee_account_id`,id??null)}/>
      </div>)}
      <div className="space-y-1"><label className="text-xs font-medium">Discount<CurrencyInput value={value.discount_amount} onValueChange={v=>update("discount_amount",v)}/></label>
        <div className="text-xs text-slate-500">{discount?`${discount.code} — ${discount.name}`:"Purchase Discount account not configured"}</div>
      </div>
    </div>
    {accounts.isError&&<p role="alert" className="text-xs text-red-700">Expense accounts could not be loaded. Retry before adding charges.</p>}
    {value.other_fee_amount>0&&<div className="grid gap-3 md:grid-cols-3"><label className="text-xs font-medium">Other charge<CurrencyInput value={value.other_fee_amount} onValueChange={v=>update("other_fee_amount",v)}/></label><SearchableSelect label="Other expense account" options={options} value={value.other_fee_account_id??undefined} onChange={id=>update("other_fee_account_id",id??null)}/><label className="text-xs font-medium">Description<input className="w-full rounded border p-2" value={value.other_fee_description} onChange={e=>update("other_fee_description",e.target.value)}/></label></div>}
    <div className="flex justify-end gap-8 text-sm font-semibold"><span>Total including charges and discount</span><span>{money(billingTotal(subtotal,tax,value))}</span></div>
  </section>;
}
