import { useQuery } from "@tanstack/react-query";
import CurrencyInput from "@/components/form/CurrencyInput";
import SearchableSelect from "@/components/form/SearchableSelect";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { billingTotal, type ReceivingBilling } from "../billing";

type Props = { value: ReceivingBilling; onChange: (next: ReceivingBilling) => void; subtotal: number; tax: number; open?: boolean };
const money = (v: number) => v.toLocaleString("id-ID", {minimumFractionDigits:2,maximumFractionDigits:2});
export default function ReceivingBillingFields({value, onChange, subtotal, tax, open = true}: Props) {
  const accounts = useQuery({
    queryKey: ["receiving-billing-expense-accounts"],
    queryFn: () => getAllAccountLookup({account_type:"EXPENSE",is_active:true,is_posting:true}),
    enabled:open,
  });
  const update = <K extends keyof ReceivingBilling>(key: K, next: ReceivingBilling[K]) => onChange({...value, [key]:next});
  const accountOptions = (accounts.data ?? []).map((a:any)=>({id:Number(a.id),label:`${a.account_code} — ${a.account_name}`,keywords:[a.account_code,a.account_name]}));
  return <section className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-3">
    <div>
      <h3 className="font-semibold text-sm">Supplier Invoice & Additional Charges</h3>
      <p className="text-xs text-slate-600">Enter the supplier document received with the goods. Complete documents auto-verify the generated invoice when Receiving is posted; incomplete documents leave it as a draft for correction.</p>
    </div>
    <div className="grid gap-3 md:grid-cols-3">
      <label className="text-xs font-medium">Supplier Invoice Number<input className="mt-1 w-full rounded border p-2" maxLength={100} value={value.supplier_invoice_number} onChange={e=>update("supplier_invoice_number",e.target.value)} placeholder="Vendor-issued invoice number"/></label>
      <label className="text-xs font-medium">Supplier Invoice Date<input className="mt-1 w-full rounded border p-2" type="date" value={value.supplier_invoice_date} onChange={e=>update("supplier_invoice_date",e.target.value)}/></label>
      <label className="text-xs font-medium">Payment Due Date<input className="mt-1 w-full rounded border p-2" type="date" value={value.supplier_invoice_due_date} onChange={e=>update("supplier_invoice_due_date",e.target.value)}/></label>
      <label className="text-xs font-medium">Faktur Pajak Number<input className="mt-1 w-full rounded border p-2" maxLength={100} value={value.tax_invoice_number} onChange={e=>update("tax_invoice_number",e.target.value)}/></label>
      <label className="text-xs font-medium">Faktur Pajak Date<input className="mt-1 w-full rounded border p-2" type="date" value={value.tax_invoice_date} onChange={e=>update("tax_invoice_date",e.target.value)}/></label>
      <label className="text-xs font-medium">Supplier Documents URL<input className="mt-1 w-full rounded border p-2" type="url" maxLength={2000} value={value.supplier_document_url} onChange={e=>update("supplier_document_url",e.target.value)} placeholder="https://..."/></label>
    </div>
    <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
      <label className="text-xs font-medium">Invoice Discount<CurrencyInput value={value.discount_amount} onValueChange={v=>update("discount_amount",v)}/></label>
      {(["shipping","admin","other"] as const).map(kind=><div key={kind} className="space-y-1">
        <label className="text-xs font-medium capitalize">{kind} Fee<CurrencyInput value={value[`${kind}_fee_amount`]} onValueChange={v=>update(`${kind}_fee_amount`,v)}/></label>
        <SearchableSelect label={`${kind} expense account`} value={value[`${kind}_fee_account_id`] ?? undefined} placeholder="Choose expense account" options={accountOptions} disabled={accounts.isLoading} onChange={id=>update(`${kind}_fee_account_id`,id ?? null)}/>
      </div>)}
    </div>
    {value.other_fee_amount > 0 && <label className="text-xs font-medium">Other Charge Description<input className="mt-1 w-full rounded border p-2" value={value.other_fee_description} maxLength={250} onChange={e=>update("other_fee_description",e.target.value)}/></label>}
    <div className="flex flex-wrap items-center justify-between gap-2 border-t pt-3 text-sm"><span>Invoice estimate (goods + PPN − discount + charges)</span><strong className="tabular-nums">{money(billingTotal(subtotal,tax,value))}</strong></div>
    <p className="text-xs text-amber-700">PPN rates shown at Receiving are estimates. Confirm the supplier's tax document; discounts affecting the PPN base may require invoice correction. Fees use the selected expense accounts, not inventory valuation.</p>
  </section>;
}
