import { Printer, SlidersHorizontal } from "lucide-react";
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
import { todayLocal } from "@/utils/dateConstraints";
import useAuthorization from "@/hooks/useAuthorization";
import useFormRecovery from "@/hooks/useFormRecovery";
import FormRecoveryActions from "@/components/form/FormRecoveryActions";
import { createPayment, eligibleInvoices, eligibleSuppliers, eligibleVouchers, getPayment, listPayments, paymentAction, updatePayment, type Payment } from "./api";

const methods = ["BANK_TRANSFER", "CASH", "CHEQUE", "CREDIT_CARD", "PETTY_CASH", "OTHER"];
const currencies = ["IDR", "USD", "SGD", "MYR", "EUR", "JPY", "CNY", "AUD"];
const today = todayLocal;
const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const emptyForm = () => ({ supplier_id:0,payment_date:today(),payment_method:"BANK_TRANSFER",currency:"IDR",total_amount:0,voucher_id:null as number|null,reference_number:"",cheque_number:"",notes:"",source_type:"LIVE",allocations:[] as any[],funding_lines:[{bank_account_id:0,amount:0}] as any[] });
const availableBalance = (row:any) => Number(row.available_balance ?? row.outstanding_balance ?? 0);
type PaymentInput = ReturnType<typeof emptyForm>;
const validPaymentInput = (v: unknown): v is PaymentInput => { const x = v as PaymentInput; return !!x && typeof x.payment_date === "string" && typeof x.supplier_id === "number" && typeof x.currency === "string" && Array.isArray(x.allocations) && Array.isArray(x.funding_lines); };
type ListAction = "approve" | "generate-journal" | "void" | "reopen" | "unpost" | "cancel-posted";

export default function PaymentListPage() {
  const navigate=useNavigate();const location=useLocation();const qc=useQueryClient();
  const { hasPermission, isSuperuser } = useAuthorization();
  const canManage = hasPermission("payment.manage");
  const admin = isSuperuser();
  const [pageSize,setPageSize]=useState(() => Number(window.localStorage.getItem("payments-page-size")) === 100 ? 100 : 50);
  const [showFilters,setShowFilters]=useState(false);
  useEffect(() => window.localStorage.setItem("payments-page-size", String(pageSize)), [pageSize]);
  const [page,setPage]=useState(1),[search,setSearch]=useState(""),[status,setStatus]=useState(""),[filterLocationId,setFilterLocationId]=useState<number>(),[open,setOpen]=useState(false),[form,setForm]=useState<any>(emptyForm()),[editingId,setEditingId]=useState<number>();
  const recovery=useFormRecovery<PaymentInput>(`payment:${editingId ? `edit:${editingId}` : "create"}`,form,open,validPaymentInput);
  const [editingInvoices,setEditingInvoices]=useState<any[]>([]);
  const returnTo=location.pathname.startsWith("/accounts-payable")?`${location.pathname}${location.search}`:"/payments";
  const editId=Number(new URLSearchParams(location.search).get("edit"))||0;
  const editPayment=useQuery({queryKey:["payment-edit",editId],queryFn:()=>getPayment(editId),enabled:editId>0,refetchOnMount:"always"});
  const payments=useQuery({queryKey:["payments",page,pageSize,search,status,filterLocationId],queryFn:()=>listPayments({page,page_size:pageSize,search:search||undefined,status:status||undefined,location_id:filterLocationId??undefined})});
  const suppliers=useQuery({queryKey:["eligible-payment-suppliers",form.currency,editingId,editingId?form.supplier_id:0],queryFn:()=>eligibleSuppliers(form.currency,editingId?form.supplier_id:undefined),enabled:open});
  const bankAccounts=useQuery({queryKey:["active-payment-bank-accounts"],queryFn:()=>listBankAccounts(true,true)});
  const invoices=useQuery({queryKey:["eligible-payment-invoices",form.supplier_id,form.currency,editingId??0],queryFn:()=>eligibleInvoices(form.supplier_id,form.currency),enabled:Boolean(form.supplier_id)&&open,refetchOnMount:"always"});
  const vouchers=useQuery({queryKey:["eligible-payment-vouchers",form.supplier_id,form.currency],queryFn:()=>eligibleVouchers(form.supplier_id,form.currency),enabled:Boolean(form.supplier_id) && !editingId && open});
  const applyVoucher=(v:any)=>setForm((current:any)=>({...current,voucher_id:v.id,allocations:(v.invoices??[]).map((inv:any)=>({supplier_invoice_id:inv.id,allocated_amount:Number(inv.allocated_amount)}))}));

  useEffect(()=>{
    const vid=(location.state as any)?.voucherId;
    if(!vid) return;
    const sid=(location.state as any)?.voucherSupplierId ?? 0;
    navigate("/payments",{replace:true,state:null});
    setEditingId(undefined);
    setForm({...emptyForm(),voucher_id:vid,supplier_id:sid});
    setOpen(true);
  },[location.state,navigate]);

  useEffect(()=>{
    if(!form.voucher_id || !vouchers.data) return;
    const matched=vouchers.data.find((v:any)=>v.id===form.voucher_id);
    if(matched) applyVoucher(matched);
  },[form.voucher_id,vouchers.data]);
  const filterLocations=useQuery({queryKey:["payments-filter-locations","active"],queryFn:()=>listLocations({is_active:true})});

  useEffect(()=>{
    const payment=editPayment.data;
    if(!editId||!payment||(editingId===editId&&open))return;
    setEditingId(editId);
    setEditingInvoices((payment.allocations??[]).map((row:any)=>({
      ...row,
      id:row.supplier_invoice_id,
      subtotal:row.current_invoice_subtotal??row.invoice_subtotal,
      tax_amount:row.current_invoice_tax_amount??row.invoice_tax_amount,
      total_amount:row.current_invoice_total??row.invoice_total,
      paid_amount:row.current_paid_amount??row.paid_amount,
      available_balance:row.current_available_balance??0,
      reserved_amount:row.current_reserved_amount??0,
    })));
    const saved=recovery.load(`payment:edit:${editId}`);
    if(saved)recovery.notifyRestored();
    setForm(saved ?? {
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
  },[editId,editPayment.data,editingId,open,recovery]);
  const closeEditor=()=>{
    setOpen(false);
    if(editId)navigate("/payments",{replace:true,state:null});
  };
  const invoiceRows=useMemo(()=>{
    const rows=new Map<number,any>();
    editingInvoices.forEach((row:any)=>rows.set(row.id,row));
    (invoices.data??[]).forEach((row:any)=>{
      const existing=rows.get(row.id);
      rows.set(row.id,{
        ...existing,
        ...row,
        // Keep only the draft allocation amount from the payment snapshot.
        // Invoice totals/balances must always come from the fresh eligible API.
        allocated_amount:existing?.allocated_amount,
      });
    });
    // A saved allocation may no longer be eligible because an invoice was paid,
    // adjusted, or reserved by another approved payment. Keep it visible for
    // correction, but never reuse its old balance as available cash.
    if (invoices.data) for (const [id, row] of rows) {
      if (!invoices.data.some((eligible:any)=>eligible.id===id)) rows.set(id,{...row,available_balance:0});
    }
    return Array.from(rows.values());
  },[editingInvoices,invoices.data]);
  const paymentRows:any[]=useMemo(()=>payments.data?.items??[],[payments.data?.items]);
  const paymentPageTotal=useMemo(()=>paymentRows.reduce((sum:number,row:any)=>sum+Number(row.total_amount||0),0),[paymentRows]);
  const paymentFilteredTotal=Number(payments.data?.summary?.total_amount??paymentPageTotal);
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

  const save=useMutation({mutationFn:async()=>{const latest=await invoices.refetch();if (latest.isError || !latest.data) throw new Error("Could not verify current invoice availability. Try again.");for(const allocation of form.allocations){const current=latest.data.find((row:any)=>row.id===allocation.supplier_invoice_id);if(!current || Number(allocation.allocated_amount)>availableBalance(current))throw new Error(`Invoice ${current?.invoice_number||allocation.supplier_invoice_id} is no longer available for this amount. Refresh the invoice selection or clear this allocation.`);}if(editId && editingId!==editId) throw new Error("Payment edit is still loading. Try again.");return editId?updatePayment(editId,{...form,voucher_id:undefined,total_amount:allocated}):editingId?updatePayment(editingId,{...form,voucher_id:undefined,total_amount:allocated}):createPayment({...form,total_amount:allocated});},onSuccess:(payment)=>{toast.success(editId||editingId?"Draft payment updated":"Payment saved as draft");recovery.clear();setOpen(false);setEditingId(undefined);setEditingInvoices([]);setForm(emptyForm());qc.invalidateQueries({queryKey:["payments"]});qc.invalidateQueries({queryKey:["payment",String(payment.id)]});qc.invalidateQueries({queryKey:["eligible-payment-invoices"]});qc.invalidateQueries({queryKey:["eligible-payment-suppliers"]});navigate(`/payments/${payment.id}`,{state:{returnTo}})},onError:(error:any)=>toast.error(error.response?.data?.detail||error.message||"Payment could not be saved")});
  const refreshAfterAction = (id: number) => {
    [
      ["payments"], ["payment", String(id)], ["payment-edit", id],
      ["eligible-payment-invoices"], ["eligible-payment-suppliers"],
      ["supplier-invoice"], ["supplier-invoices"], ["accounts-payable-aging"],
      ["finance-dashboard"], ["cash-flow"], ["cash-accounts"],
      ["journal-entries"], ["general-ledger"], ["trial-balance"],
      ["balance-sheet"], ["dashboard", "overview"],
    ].forEach((queryKey) => qc.invalidateQueries({ queryKey }));
  };
  const rowAction = useMutation({
    mutationFn: async ({ id, name }: { id: number; name: ListAction }) => {
      const latest: Payment = await getPayment(id);
      const allowed = latest.allowed_actions ?? {};
      const permitted = name === "unpost" || name === "cancel-posted"
        ? admin && latest.status === "POSTED" && Boolean(latest.journal_entry_id)
        : name === "reopen"
          ? admin && latest.status === "APPROVED"
          : allowed[({
              approve: "can_approve",
              "generate-journal": "can_generate_journal",
              void: "can_void",
            } as Record<string, string>)[name]];
      if (!canManage || !permitted) throw new Error("This action is no longer available for the payment.");
      if (name === "approve" && latest.allocation_exception_rows?.length) {
        throw new Error("An invoice allocation needs correction. Open the payment to review it before continuing.");
      }
      const label: Record<ListAction, string> = {
        approve: "Approve and create a draft journal",
        "generate-journal": "Create the missing draft journal",
        void: "Void the payment",
        reopen: "Reopen the payment as a draft",
        unpost: "Unpost the payment and restore invoice balances",
        "cancel-posted": "Cancel the posted payment and remove its GL impact",
      };
      const invoices = latest.allocations.map((line: any) =>
        `${line.invoice_number ?? line.supplier_invoice_id}: ${money(line.allocated_amount)}`
      ).join("\n");
      const funding = latest.funding_lines.map((line: any) =>
        `${line.bank_name ?? "Account"} ${line.account_number ?? ""}: ${money(line.amount)}`
      ).join("\n");
      if (!window.confirm(
        `${label[name]}?\n\n${latest.payment_number} · ${latest.supplier_name}\nAmount: ${money(latest.total_amount)} ${latest.currency}\n\nInvoices:\n${invoices || "None"}\n\nFunding:\n${funding || "None"}`
      )) return { id, name, cancelled: true };
      if (name === "approve") {
        await paymentAction(id, "approve");
        try {
          await paymentAction(id, "generate-journal");
        } catch (error: any) {
          throw Object.assign(error, { paymentApproved: true });
        }
      } else {
        await paymentAction(id, name);
      }
      return { id, name, cancelled: false };
    },
    onSuccess: ({ id, name, cancelled }) => {
      if (cancelled) return;
      toast.success(name === "approve"
        ? "Payment approved and draft journal created."
        : `Payment ${name.replaceAll("-", " ")} complete.`);
      refreshAfterAction(id);
    },
    onError: (error: any, { id }) => {
      toast.error(error?.response?.data?.detail || error?.message || "Payment action failed.");
      refreshAfterAction(id);
    },
  });
  const runRowAction = (id: number, name: ListAction) => {
    if (rowAction.isPending) return;
    rowAction.mutate({ id, name });
  };

  const submit=()=>{if(!form.supplier_id)return toast.error("Select a supplier");if(!form.payment_date)return toast.error("Payment Date is required");if(!form.allocations.length||allocated<=0)return toast.error("Select at least one supplier invoice");if(invoices.isFetching)return toast.error("Invoice balances are still refreshing");if(form.allocations.some((row:any)=>Number(row.allocated_amount)>availableBalance(invoiceRows.find((invoice:any)=>invoice.id===row.supplier_invoice_id))))return toast.error("An allocated invoice is no longer available. Clear or correct it before saving.");if(bankAccounts.isLoading)return toast.error("Funding accounts are still loading");if(bankAccounts.isError)return toast.error("Funding accounts could not be loaded");if(!eligibleBankAccounts.length)return toast.error("No active payment account with a linked COA is available for this currency");if(funded!==allocated)return toast.error("Funding total must equal selected invoice allocations");if(form.funding_lines.some((row:any)=>!row.bank_account_id||row.amount<=0))return toast.error("Complete every funding line");if(form.funding_lines.some((row:any)=>!eligibleBankAccountIds.has(row.bank_account_id)))return toast.error("Select only payment accounts with a valid linked COA");save.mutate()};

  return <>
    <PageHeader title="Payments" description="Choose a supplier, select one or more available invoices, then fund and post the payment." actions={<>
<Button onClick={()=>{if(editId)navigate("/payments",{replace:true,state:null});setEditingId(undefined);setEditingInvoices([]);const saved=recovery.load("payment:create");setForm(saved??emptyForm());if(saved)recovery.notifyRestored();setOpen(true)}}>Create Payment</Button>
<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</>}/>
    <div className="grid gap-3 sm:grid-cols-3"><Card><div className="text-xs font-medium uppercase tracking-wide text-slate-500">Filtered Payments</div><div className="mt-1 text-xl font-semibold">{payments.data?.total_items??0}</div></Card><Card><div className="text-xs font-medium uppercase tracking-wide text-slate-500">Payment Total</div><div className="mt-1 text-xl font-semibold tabular-nums">{money(paymentFilteredTotal)}</div></Card><Card><div className="text-xs font-medium uppercase tracking-wide text-slate-500">Visible Page Total</div><div className="mt-1 text-xl font-semibold tabular-nums">{money(paymentPageTotal)}</div></Card></div>
    <Card className="p-3"><div className="mb-2 flex flex-wrap items-end gap-2"><input aria-label="Search payments" className={`${input} min-w-[260px] flex-1`} placeholder="Search payment, supplier, invoice, cheque or reference" value={search} onChange={e=>{setSearch(e.target.value);setPage(1)}}/><select aria-label="Payment status" className={`${input} w-auto min-w-[150px]`} value={status} onChange={e=>{setStatus(e.target.value);setPage(1)}}><option value="">All statuses</option>{["DRAFT","APPROVED","POSTED","VOID"].map(value=><option key={value}>{value}</option>)}</select><Button type="button" size="sm" variant="outline" aria-expanded={showFilters} onClick={() => setShowFilters(value=>!value)}><SlidersHorizontal size={15}/> Filters{filterLocationId?" (1)":""}</Button></div>{showFilters && <div className="mb-2 max-w-sm border-t border-slate-100 pt-2"><SearchableSelect label="Location" value={filterLocationId} disabled={filterLocations.isLoading} placeholder={filterLocations.isLoading?"Loading locations...":"Type location code or name..."} options={(filterLocations.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}))} onChange={id=>{setFilterLocationId(id);setPage(1)}}/></div>}<Table className="min-w-[820px]" containerClassName="border-0 shadow-none"><THead><TR className="whitespace-nowrap"><TH>Payment</TH><TH>Supplier</TH><TH numeric>Amount</TH><TH numeric>Allocation / Funding</TH><TH>Status</TH><TH numeric>Action</TH></TR></THead><TBody>{payments.data?.items.map((row:any)=><TR key={row.id} className="whitespace-nowrap"><TD><TableCellStack primary={<Link className={TABLE_UI.documentLink} to={`/payments/${row.id}`} state={{returnTo}}>{row.payment_number}</Link>} secondary={`${row.payment_date} · ${row.payment_method.replaceAll("_"," ")}`}/></TD><TD className="font-medium">{row.supplier_name}</TD><TD numeric className="font-semibold">{money(row.total_amount)}</TD><TD numeric><TableCellStack primary={`Allocated ${money(row.allocated_amount)}`} secondary={`Funded ${money(row.funded_amount)}`}/></TD><TD>{row.status}</TD><TD><div className="flex items-center justify-end gap-1" role="group" aria-label={`Actions for ${row.payment_number}`}>
  <Button size="xs" variant="outline" onClick={() => navigate(`/payments/${row.id}`, { state: { returnTo } })}>View</Button>
  {canManage && row.status === "DRAFT" && <Button size="xs" disabled={rowAction.isPending} loading={rowAction.isPending && rowAction.variables?.id === row.id && rowAction.variables?.name === "approve"} onClick={() => runRowAction(row.id, "approve")}>Approve</Button>}
  {(canManage || admin || hasPermission("journal.manage")) && <select className="h-7 rounded border border-slate-300 bg-white px-1 text-xs" aria-label={`More actions for ${row.payment_number}`} value="" disabled={rowAction.isPending} onChange={event => {const action=event.target.value; if(action==="edit") navigate(`/payments?edit=${row.id}`); else if(action==="open-journal") navigate(`/journal-entries/${row.journal_entry_id}`); else if(action) runRowAction(row.id, action as ListAction);}}>
    <option value="">More actions</option>
    {canManage && row.status === "DRAFT" && <option value="edit">Edit</option>}
    {canManage && row.status === "APPROVED" && !row.journal_entry_id && <option value="generate-journal">Create journal</option>}
    {hasPermission("journal.manage") && row.status === "APPROVED" && Boolean(row.journal_entry_id) && <option value="open-journal">Open journal to post</option>}
    {admin && row.status === "APPROVED" && <option value="reopen">Reopen</option>}
    {canManage && ["DRAFT", "APPROVED"].includes(row.status) && <option value="void">Void payment</option>}
    {admin && row.status === "POSTED" && <option value="unpost">Unpost</option>}
    {admin && row.status === "POSTED" && <option value="cancel-posted">Cancel posted payment</option>}
  </select>}
</div></TD></TR>)}</TBody></Table><div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2 text-xs"><label>Rows per page <select className="ml-1 rounded border border-slate-300 bg-white px-2 py-1" value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setPage(1)}}><option value={50}>50</option><option value={100}>100</option></select></label><div className="flex items-center gap-2"><span>{payments.data?.total_items??0} payments · Page {page} of {Math.max(payments.data?.total_pages??0,1)}</span><Button size="sm" variant="outline" disabled={!payments.data?.has_previous} onClick={()=>setPage(page-1)}>Previous</Button><Button size="sm" variant="outline" disabled={!payments.data?.has_next} onClick={()=>setPage(page+1)}>Next</Button></div></div></Card>

    <Dialog open={open} onOpenChange={next=>{if(save.isPending)return;if(!next)closeEditor();else setOpen(true)}}><DialogContent className="max-h-[92vh] max-w-6xl overflow-y-auto"><DialogHeader><DialogTitle>{editingId?"Edit Draft Supplier Payment":"Create Supplier Payment"}</DialogTitle></DialogHeader><DialogBody className="space-y-6">
      <div className="grid gap-3 md:grid-cols-4"><SearchableSelect label="Supplier" required value={form.supplier_id||undefined} disabled={suppliers.isLoading} placeholder={suppliers.isLoading?"Loading suppliers...":"Type supplier code or name..."} options={supplierOptions} onChange={value=>setForm({...form,supplier_id:value??0,allocations:[]})}/><label className="text-sm">Payment Date<input type="date" data-allow-past-date="true" className={input} value={form.payment_date} onChange={e=>setForm({...form,payment_date:e.target.value})}/></label><label className="text-sm">Payment Method<select className={input} value={form.payment_method} onChange={e=>setForm({...form,payment_method:e.target.value})}>{methods.map(value=><option key={value}>{value}</option>)}</select></label><label className="text-sm">Currency<select className={input} value={form.currency} onChange={e=>setForm({...form,currency:e.target.value,supplier_id:editingId?form.supplier_id:0,allocations:[]})}>{currencies.map(value=><option key={value}>{value}</option>)}</select></label><label className="text-sm md:col-span-2">Reference Number<input className={input} value={form.reference_number} onChange={e=>setForm({...form,reference_number:e.target.value})}/></label>{form.payment_method==="CHEQUE"&&<label className="text-sm">Cheque Number<input className={input} value={form.cheque_number} onChange={e=>setForm({...form,cheque_number:e.target.value})}/></label>}</div>

      {form.supplier_id && (
        <section className="space-y-2">
          <h3 className="font-semibold">Approved Payment Vouchers</h3>
          <p className="text-sm text-slate-500">Select an approved voucher to import its invoices into this payment.</p>
          {vouchers.isLoading && <div className="text-xs text-slate-500">Loading approved vouchers...</div>}
          {vouchers.data?.length ? (
            <div className="flex flex-wrap gap-2">
              {vouchers.data.map((v:any)=>(
                <button key={v.id} type="button" className={`max-w-xs rounded-md border px-3 py-2 text-left text-sm hover:bg-slate-50 ${form.voucher_id===v.id?"border-emerald-600 bg-emerald-50 font-medium":"border-slate-200 bg-white"}`} onClick={()=>applyVoucher(v)}>
                  <div className="font-medium">{v.voucher_number} <span className="text-xs text-slate-500">{v.voucher_date}</span></div>
                  <div className="text-xs text-slate-500">{v.invoices.length} invoices • {money(v.allocated_amount)}</div>
                </button>
              ))}
            </div>
          ) : null}
        </section>
      )}
      <section><div className="mb-2 flex flex-wrap items-end justify-between gap-2"><div><h3 className="font-semibold">Available Supplier Invoices</h3><p className="text-sm text-slate-500">Invoice Total and Available include PPN, less discounts, withholding, and payments. Enter any amount up to Available; a smaller amount is a partial payment.</p></div>{form.supplier_id&&<div className="flex gap-2"><Button size="sm" variant="outline" disabled={!invoiceRows.length} onClick={selectAll}>Select All Available</Button><Button size="sm" variant="outline" disabled={!selectedIds.size} onClick={clearAll}>Clear</Button></div>}</div>
        {!form.supplier_id?<div className="rounded border border-dashed p-8 text-center text-sm text-slate-500">Select a supplier to load invoices.</div>:invoices.isLoading?<div className="rounded border p-8 text-center text-sm text-slate-500">Loading supplier invoices…</div>:!invoiceRows.length?<div className="rounded border p-8 text-center text-sm text-slate-500">This supplier has no available verified/posted invoices.</div>:<div className="overflow-x-auto rounded border"><table className="min-w-[1320px] w-full text-sm"><thead><tr><th className="w-12">Pay</th><th>Invoice</th><th>Supplier Ref</th><th>Date</th><th>Due</th><th>Subtotal</th><th>PPN</th><th>Invoice Total</th><th>Paid</th><th>Reserved</th><th>Available</th><th>Allocated Amount</th></tr></thead><tbody>{invoiceRows.map((row:any)=>{const current=form.allocations.find((allocation:any)=>allocation.supplier_invoice_id===row.id)?.allocated_amount??0;const selected=selectedIds.has(row.id);const available=availableBalance(row);return <tr key={row.id} className={`border-t ${selected?"bg-emerald-50/60":""}`}><td className="text-center"><input aria-label={`Pay ${row.invoice_number}`} type="checkbox" checked={selected} onChange={e=>toggleInvoice(row,e.target.checked)}/></td><td><Link className="font-medium text-emerald-700 hover:underline" to={`/supplier-invoices/${row.id}`}>{row.invoice_number}</Link></td><td>{row.supplier_invoice_number||"—"}</td><td>{row.invoice_date}</td><td>{row.due_date||"—"}</td><td className="text-right">{money(row.subtotal)}</td><td className="text-right">{money(row.tax_amount)}</td><td className="text-right font-semibold">{money(row.total_amount)}</td><td className="text-right">{money(row.paid_amount)}</td><td className="text-right">{money(row.reserved_amount)}</td><td className={`text-right font-medium ${selected&&available<=0?"text-red-700":""}`}>{money(available)}{selected&&available<=0&&<span className="block text-xs">No longer available</span>}</td><td className="w-44"><CurrencyInput value={Number(current)} onValueChange={value=>setAllocation(row.id,Math.min(value,available))}/></td></tr>})}</tbody></table></div>}
      </section>

      <section className="space-y-3"><div className="flex flex-wrap items-end justify-between gap-2"><div><h3 className="font-semibold">Funding Accounts</h3><p className="text-sm text-slate-500">Select a registered account only. Its linked COA is applied automatically; accountants do not enter or memorize COA numbers.</p></div>{form.funding_lines.length===1&&<Button size="sm" variant="outline" disabled={allocated<=0||!eligibleBankAccounts.length} onClick={useAllocatedAsFunding}>Use Selected Total</Button>}</div>{!bankAccounts.isLoading&&!eligibleBankAccounts.length&&<div className="flex flex-wrap items-center justify-between gap-3 rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900"><span>No active funding account with a linked COA is available for {form.currency}. Register a location or a global corporate account in Cash &amp; Bank.</span><Button size="sm" variant="outline" onClick={()=>navigate("/cash-bank/accounts")}>Open Cash &amp; Bank</Button></div>}{form.funding_lines.map((row:any,index:number)=><div key={index} className="grid gap-3 rounded border p-3 md:grid-cols-[minmax(0,1fr)_220px_auto]"><SearchableSelect label="Payment Account" required value={row.bank_account_id||undefined} disabled={!eligibleBankAccounts.length} placeholder="Type bank, account number, or COA..." options={fundingOptions} onChange={value=>setFunding(index,{bank_account_id:value??0})}/><CurrencyInput value={Number(row.amount||0)} onValueChange={value=>setFunding(index,{amount:value})}/><Button variant="outline" disabled={form.funding_lines.length===1} onClick={()=>setForm({...form,funding_lines:form.funding_lines.filter((_:any,i:number)=>i!==index)})}>Remove</Button></div>)}<Button variant="outline" disabled={!eligibleBankAccounts.length} onClick={()=>setForm({...form,funding_lines:[...form.funding_lines,{bank_account_id:0,amount:0}]})}>Add Funding Account</Button></section>
      <div className="grid gap-3 rounded border border-slate-200 bg-slate-50 p-4 text-right md:grid-cols-4"><div className="text-left"><div className="text-xs font-medium uppercase tracking-wide text-slate-500">Payment Total</div><div className="mt-1 text-2xl font-bold tabular-nums">{money(allocated)}</div></div><div>Selected to Pay<br/><strong>{money(allocated)}</strong></div><div>Funding Total<br/><strong>{money(funded)}</strong></div><div>Difference<br/><strong className={funded===allocated?"text-emerald-700":"text-amber-700"}>{money(funded-allocated)}</strong></div></div>
      <label className="block text-sm">Notes<textarea className="mt-1 min-h-20 w-full rounded border p-2" value={form.notes} onChange={e=>setForm({...form,notes:e.target.value})}/></label>
    </DialogBody><DialogFooter><FormRecoveryActions failed={recovery.failed} disabled={save.isPending} onDiscard={()=>{recovery.clear();closeEditor();setEditingId(undefined);setEditingInvoices([]);setForm(emptyForm())}} /><Button variant="outline" disabled={save.isPending} onClick={closeEditor}>Close</Button><Button loading={save.isPending} onClick={submit}>{editingId?"Save Changes":"Save Draft"}</Button></DialogFooter></DialogContent></Dialog>
  </>;
}
