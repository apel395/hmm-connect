import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { TABLE_UI } from "@/config/tableUi";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import SearchableSelect from "@/components/form/SearchableSelect";
import { listBankAccounts } from "@/modules/finance/cash-flow/bankAccountApi";
import { listLocations } from "@/modules/admin/organization/api";
import { isBeforeToday, todayLocal } from "@/utils/dateConstraints";
import { createPayment, eligibleInvoices, eligibleSuppliers, listPayments, updatePayment } from "./api";

const methods = ["BANK_TRANSFER", "CASH", "CHEQUE", "CREDIT_CARD", "PETTY_CASH", "OTHER"];
const today = todayLocal;
const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const emptyForm = () => ({ supplier_id:0,payment_date:today(),payment_method:"BANK_TRANSFER",currency:"IDR",total_amount:0,reference_number:"",cheque_number:"",notes:"",source_type:"LIVE",allocations:[] as any[],funding_lines:[{bank_account_id:0,amount:0}] as any[] });
const availableBalance = (row:any) => Number(row.available_balance ?? row.outstanding_balance ?? 0);

export default function PaymentListPage() {
  const navigate=useNavigate();const location=useLocation();const qc=useQueryClient();
  const [page,setPage]=useState(1),[search,setSearch]=useState(""),[status,setStatus]=useState(""),[filterLocationId,setFilterLocationId]=useState<number>(),[open,setOpen]=useState(false),[form,setForm]=useState<any>(emptyForm()),[editingId,setEditingId]=useState<number>();
  const [editingInvoices,setEditingInvoices]=useState<any[]>([]);
  const returnTo=location.pathname.startsWith("/accounts-payable")?`${location.pathname}${location.search}`:"/payments";
  const payments=useQuery({queryKey:["payments",page,search,status,filterLocationId],queryFn:()=>listPayments({page,page_size:20,search:search||undefined,status:status||undefined,location_id:filterLocationId??undefined})});
  const suppliers=useQuery({queryKey:["eligible-payment-suppliers",form.currency,editingId,editingId?form.supplier_id:0],queryFn:()=>eligibleSuppliers(form.currency,editingId?form.supplier_id:undefined),enabled:open});
  const bankAccounts=useQuery({queryKey:["active-payment-bank-accounts"],queryFn:()=>listBankAccounts(true,true)});
  const invoices=useQuery({queryKey:["eligible-payment-invoices",form.supplier_id,form.currency],queryFn:()=>eligibleInvoices(form.supplier_id,form.currency),enabled:Boolean(form.supplier_id)});
  const filterLocations=useQuery({queryKey:["payments-filter-locations","active"],queryFn:()=>listLocations({is_active:true})});

  useEffect(()=>{
    const payment=(location.state as any)?.editPayment;
    if(!payment)return;
    setEditingId(payment.id);
    setEditingInvoices((payment.allocations??[]).map((row:any)=>({
      ...row,
      id:row.supplier_invoice_id,
      total_amount:row.total_amount??row.invoice_total,
      available_balance:row.available_balance??row.outstanding_balance??row.allocated_amount,
      reserved_amount:row.reserved_amount??0,
    })));
    setForm({
      supplier_id:payment.supplier_id,
      payment_date:payment.payment_date,
      payment_method:payment.payment_method,
      currency:payment.currency,
      total_amount:Number(payment.total_amount||0),
      reference_number:payment.reference_number||"",
      cheque_number:payment.cheque_number||"",
      notes:payment.notes||"",
      source_type:payment.source_type||"LIVE",
      allocations:(payment.allocations??[]).map((row:any)=>({supplier_invoice_id:row.supplier_invoice_id,allocated_amount:Number(row.allocated_amount||0)})),
      funding_lines:(payment.funding_lines??[]).map((row:any)=>({bank_account_id:row.bank_account_id,amount:Number(row.amount||0)})),
    });
    setOpen(true);
    navigate("/payments",{replace:true,state:null});
  },[location.state,navigate]);
  const invoiceRows=useMemo(()=>{
    const rows=new Map<number,any>();
    editingInvoices.forEach((row:any)=>rows.set(row.id,row));
    (invoices.data??[]).forEach((row:any)=>rows.set(row.id,row));
    return Array.from(rows.values());
  },[editingInvoices,invoices.data]);
  const allocated=useMemo(()=>form.allocations.reduce((sum:number,row:any)=>sum+Number(row.allocated_amount||0),0),[form.allocations]);
  const funded=useMemo(()=>form.funding_lines.reduce((sum:number,row:any)=>sum+Number(row.amount||0),0),[form.funding_lines]);
  const selectedIds=new Set(form.allocations.filter((row:any)=>Number(row.allocated_amount)>0).map((row:any)=>row.supplier_invoice_id));
  const eligibleBankAccounts=(bankAccounts.data??[]).filter(bank=>bank.currency===form.currency);
  const eligibleBankAccountIds=new Set(eligibleBankAccounts.map(bank=>bank.id));
  const supplierOptions=(suppliers.data??[]).map((supplier:any)=>({id:supplier.id,label:`${supplier.code} — ${supplier.name}`,keywords:[supplier.code??"",supplier.name??""]}));
  const fundingOptions=eligibleBankAccounts.map((bank:any)=>({id:bank.id,label:`${bank.bank_name} — ${bank.account_name} — ${bank.account_number}`,keywords:[bank.bank_name??"",bank.account_name??"",bank.account_number??"",bank.coa_account_code??""]}));

  const setAllocation=(invoiceId:number,amount:number)=>setForm((current:any)=>({...current,allocations:amount>0?[...current.allocations.filter((row:any)=>row.supplier_invoice_id!==invoiceId),{supplier_invoice_id:invoiceId,allocated_amount:amount}]:current.allocations.filter((row:any)=>row.supplier_invoice_id!==invoiceId)}));
  const toggleInvoice=(row:any,checked:boolean)=>setAllocation(row.id,checked?availableBalance(row):0);
  const selectAll=()=>setForm((current:any)=>({...current,allocations:invoiceRows.map((row:any)=>({supplier_invoice_id:row.id,allocated_amount:availableBalance(row)}))}));
  const clearAll=()=>setForm((current:any)=>({...current,allocations:[]}));
  const setFunding=(index:number,patch:any)=>setForm((current:any)=>{
    const fundingLines=current.funding_lines.map((row:any,i:number)=>i===index?{...row,...patch}:row);
    if (Object.prototype.hasOwnProperty.call(patch,"amount")&&fundingLines.length===1&&current.allocations.length===1) {
      const allocation=current.allocations[0];
      const invoice=invoiceRows.find((row:any)=>row.id===allocation.supplier_invoice_id);
      const amount=Math.min(Math.max(0,Number(patch.amount)||0),invoice?availableBalance(invoice):Number(patch.amount)||0);
      return {...current,funding_lines:fundingLines,allocations:[{...allocation,allocated_amount:amount}]};
    }
    return {...current,funding_lines:fundingLines};
  });
  const useAllocatedAsFunding=()=>setForm((current:any)=>({...current,funding_lines:current.funding_lines.length===1?[{...current.funding_lines[0],amount:allocated}]:current.funding_lines}));

  const save=useMutation({mutationFn:()=>editingId?updatePayment(editingId,{...form,total_amount:allocated}):createPayment({...form,total_amount:allocated}),onSuccess:(payment)=>{toast.success(editingId?"Draft payment updated":"Payment saved as draft");setOpen(false);setEditingId(undefined);setEditingInvoices([]);setForm(emptyForm());qc.invalidateQueries({queryKey:["payments"]});qc.invalidateQueries({queryKey:["payment",String(payment.id)]});qc.invalidateQueries({queryKey:["eligible-payment-invoices"]});qc.invalidateQueries({queryKey:["eligible-payment-suppliers"]});navigate(`/payments/${payment.id}`,{state:{returnTo}})},onError:(error:any)=>toast.error(error.response?.data?.detail||"Payment could not be saved")});
  const submit=()=>{if(!form.supplier_id)return toast.error("Select a supplier");if(!form.payment_date||(!editingId&&isBeforeToday(form.payment_date)))return toast.error("Payment Date cannot be before today");if(!form.allocations.length||allocated<=0)return toast.error("Select at least one supplier invoice");if(bankAccounts.isLoading)return toast.error("Funding accounts are still loading");if(bankAccounts.isError)return toast.error("Funding accounts could not be loaded");if(!eligibleBankAccounts.length)return toast.error("No active payment account with a linked COA is available for this currency");if(funded!==allocated)return toast.error("Funding total must equal selected invoice allocations");if(form.funding_lines.some((row:any)=>!row.bank_account_id||row.amount<=0))return toast.error("Complete every funding line");if(form.funding_lines.some((row:any)=>!eligibleBankAccountIds.has(row.bank_account_id)))return toast.error("Select only payment accounts with a valid linked COA");save.mutate()};

  return <>
    <PageHeader title="Payments" description="Choose a supplier, select one or more available invoices, then fund and post the payment." actions={<Button onClick={()=>{setEditingId(undefined);setEditingInvoices([]);setForm(emptyForm());setOpen(true)}}>Create Payment</Button>}/>
    <Card><div className="mb-4 grid gap-3 md:grid-cols-4"><input className={input} placeholder="Search payment number or reference" value={search} onChange={e=>{setSearch(e.target.value);setPage(1)}}/><select className={input} value={status} onChange={e=>{setStatus(e.target.value);setPage(1)}}><option value="">All statuses</option>{["DRAFT","APPROVED","POSTED","VOID"].map(value=><option key={value}>{value}</option>)}</select><div className="md:col-span-2"><SearchableSelect label="Location" value={filterLocationId} disabled={filterLocations.isLoading} placeholder={filterLocations.isLoading?"Loading locations...":"Type location code or name..."} options={(filterLocations.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}))} onChange={id=>{setFilterLocationId(id);setPage(1)}}/></div></div><Table className="min-w-[820px]" containerClassName="border-0 shadow-none"><THead><TR className="whitespace-nowrap"><TH>Payment</TH><TH>Supplier</TH><TH numeric>Amount</TH><TH numeric>Allocation / Funding</TH><TH>Status</TH><TH numeric>Action</TH></TR></THead><TBody>{payments.data?.items.map((row:any)=><TR key={row.id} className="whitespace-nowrap"><TD><TableCellStack primary={<Link className={TABLE_UI.documentLink} to={`/payments/${row.id}`} state={{returnTo}}>{row.payment_number}</Link>} secondary={`${row.payment_date} · ${row.payment_method.replaceAll("_"," ")}`}/></TD><TD className="font-medium">{row.supplier_name}</TD><TD numeric className="font-semibold">{money(row.total_amount)}</TD><TD numeric><TableCellStack primary={`Allocated ${money(row.allocated_amount)}`} secondary={`Funded ${money(row.funded_amount)}`}/></TD><TD>{row.status}</TD><TD><div className="flex justify-end"><Button size="xs" variant="outline" onClick={()=>navigate(`/payments/${row.id}`,{state:{returnTo}})}>View</Button></div></TD></TR>)}</TBody></Table><div className="mt-4 flex justify-end gap-2"><Button variant="outline" disabled={!payments.data?.has_previous} onClick={()=>setPage(page-1)}>Previous</Button><Button variant="outline" disabled={!payments.data?.has_next} onClick={()=>setPage(page+1)}>Next</Button></div></Card>

    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-h-[92vh] max-w-6xl overflow-y-auto"><DialogHeader><DialogTitle>{editingId?"Edit Draft Supplier Payment":"Create Supplier Payment"}</DialogTitle></DialogHeader><DialogBody className="space-y-6">
      <div className="grid gap-3 md:grid-cols-4"><SearchableSelect label="Supplier" required value={form.supplier_id||undefined} disabled={suppliers.isLoading} placeholder={suppliers.isLoading?"Loading suppliers...":"Type supplier code or name..."} options={supplierOptions} onChange={value=>setForm({...form,supplier_id:value??0,allocations:[]})}/><label className="text-sm">Payment Date<input type="date" min={editingId?undefined:today()} className={input} value={form.payment_date} onChange={e=>setForm({...form,payment_date:e.target.value})}/></label><label className="text-sm">Payment Method<select className={input} value={form.payment_method} onChange={e=>setForm({...form,payment_method:e.target.value})}>{methods.map(value=><option key={value}>{value}</option>)}</select></label><label className="text-sm">Currency<input className={input} value={form.currency} maxLength={3} onChange={e=>setForm({...form,currency:e.target.value.toUpperCase(),supplier_id:editingId?form.supplier_id:0,allocations:[]})}/></label><label className="text-sm md:col-span-2">Reference Number<input className={input} value={form.reference_number} onChange={e=>setForm({...form,reference_number:e.target.value})}/></label>{form.payment_method==="CHEQUE"&&<label className="text-sm">Cheque Number<input className={input} value={form.cheque_number} onChange={e=>setForm({...form,cheque_number:e.target.value})}/></label>}</div>

      <section><div className="mb-2 flex flex-wrap items-end justify-between gap-2"><div><h3 className="font-semibold">Available Supplier Invoices</h3><p className="text-sm text-slate-500">Enter any amount up to Available. Full settlement is not required, and the remaining balance stays available for a later payment.</p></div>{form.supplier_id&&<div className="flex gap-2"><Button size="sm" variant="outline" disabled={!invoiceRows.length} onClick={selectAll}>Select All Available</Button><Button size="sm" variant="outline" disabled={!selectedIds.size} onClick={clearAll}>Clear</Button></div>}</div>
        {!form.supplier_id?<div className="rounded border border-dashed p-8 text-center text-sm text-slate-500">Select a supplier to load invoices.</div>:invoices.isLoading?<div className="rounded border p-8 text-center text-sm text-slate-500">Loading supplier invoices…</div>:!invoiceRows.length?<div className="rounded border p-8 text-center text-sm text-slate-500">This supplier has no available verified/posted invoices.</div>:<div className="overflow-x-auto rounded border"><table className="min-w-[1120px] w-full text-sm"><thead><tr><th className="w-12">Pay</th><th>Invoice</th><th>Supplier Ref</th><th>Date</th><th>Due</th><th>Total</th><th>Paid</th><th>Reserved</th><th>Available</th><th>Allocated Amount</th></tr></thead><tbody>{invoiceRows.map((row:any)=>{const current=form.allocations.find((allocation:any)=>allocation.supplier_invoice_id===row.id)?.allocated_amount??0;const selected=selectedIds.has(row.id);const available=availableBalance(row);return <tr key={row.id} className={`border-t ${selected?"bg-emerald-50/60":""}`}><td className="text-center"><input aria-label={`Pay ${row.invoice_number}`} type="checkbox" checked={selected} onChange={e=>toggleInvoice(row,e.target.checked)}/></td><td><Link className="font-medium text-emerald-700 hover:underline" to={`/supplier-invoices/${row.id}`}>{row.invoice_number}</Link></td><td>{row.supplier_invoice_number||"—"}</td><td>{row.invoice_date}</td><td>{row.due_date||"—"}</td><td className="text-right">{money(row.total_amount)}</td><td className="text-right">{money(row.paid_amount)}</td><td className="text-right">{money(row.reserved_amount)}</td><td className="text-right font-medium">{money(available)}</td><td className="w-44"><CurrencyInput value={Number(current)} onValueChange={value=>setAllocation(row.id,Math.min(value,available))}/></td></tr>})}</tbody></table></div>}
      </section>

      <section className="space-y-3"><div className="flex flex-wrap items-end justify-between gap-2"><div><h3 className="font-semibold">Funding Accounts</h3><p className="text-sm text-slate-500">Select a registered account only. Its linked COA is applied automatically; accountants do not enter or memorize COA numbers.</p></div>{form.funding_lines.length===1&&<Button size="sm" variant="outline" disabled={allocated<=0||!eligibleBankAccounts.length} onClick={useAllocatedAsFunding}>Use Selected Total</Button>}</div>{!bankAccounts.isLoading&&!eligibleBankAccounts.length&&<div className="flex flex-wrap items-center justify-between gap-3 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"><span>No active funding account with a linked COA is available for {form.currency}. Register a location or a global corporate account in Cash &amp; Bank.</span><Button size="sm" variant="outline" onClick={()=>navigate("/cash-bank/accounts")}>Open Cash &amp; Bank</Button></div>}{form.funding_lines.map((row:any,index:number)=><div key={index} className="grid gap-3 rounded border p-3 md:grid-cols-[minmax(0,1fr)_220px_auto]"><SearchableSelect label="Payment Account" required value={row.bank_account_id||undefined} disabled={!eligibleBankAccounts.length} placeholder="Type bank, account number, or COA..." options={fundingOptions} onChange={value=>setFunding(index,{bank_account_id:value??0})}/><CurrencyInput value={Number(row.amount||0)} onValueChange={value=>setFunding(index,{amount:value})}/><Button variant="outline" disabled={form.funding_lines.length===1} onClick={()=>setForm({...form,funding_lines:form.funding_lines.filter((_:any,i:number)=>i!==index)})}>Remove</Button></div>)}<Button variant="outline" disabled={!eligibleBankAccounts.length} onClick={()=>setForm({...form,funding_lines:[...form.funding_lines,{bank_account_id:0,amount:0}]})}>Add Funding Account</Button></section>
      <div className="grid gap-3 rounded bg-slate-50 p-4 text-right md:grid-cols-3"><div>Selected Invoices<br/><strong>{money(allocated)}</strong></div><div>Funding Total<br/><strong>{money(funded)}</strong></div><div>Difference<br/><strong className={funded===allocated?"text-emerald-700":"text-amber-700"}>{money(funded-allocated)}</strong></div></div>
      <label className="block text-sm">Notes<textarea className="mt-1 min-h-20 w-full rounded border p-2" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label>
    </DialogBody><DialogFooter><Button variant="outline" onClick={()=>setOpen(false)}>Cancel</Button><Button loading={save.isPending} onClick={submit}>{editingId?"Save Changes":"Save Draft"}</Button></DialogFooter></DialogContent></Dialog>
  </>;
}
