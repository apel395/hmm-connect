import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import CurrencyInput from "@/components/form/CurrencyInput";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { listInvoices } from "@/modules/finance/supplier-invoices/api";
import { createSupplierAdjustment, listSupplierAdjustments, supplierAdjustmentAction } from "./api";

const today = () => new Date().toISOString().slice(0, 10);
const money = (value: unknown) => Number(value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const emptyForm = () => ({ adjustment_type: "CREDIT_NOTE", supplier_invoice_id: 0, adjustment_date: today(), amount: 0, adjustment_account_id: 0, reason: "", notes: "" });

export default function SupplierAdjustmentsPage() {
  const queryClient = useQueryClient();
  const [form, setForm] = useState<any>(emptyForm());
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const refreshFinance = () => {
    queryClient.invalidateQueries({ queryKey: ["supplier-adjustments"] });
    queryClient.invalidateQueries({ queryKey: ["supplier-invoices"] });
    queryClient.invalidateQueries({ queryKey: ["eligible-payment-invoices"] });
    queryClient.invalidateQueries({ queryKey: ["accounts-payable-aging"] });
    queryClient.invalidateQueries({ queryKey: ["finance-dashboard"] });
    queryClient.invalidateQueries({ queryKey: ["journal-entries"] });
    queryClient.invalidateQueries({ queryKey: ["general-ledger"] });
    queryClient.invalidateQueries({ queryKey: ["trial-balance"] });
    queryClient.invalidateQueries({ queryKey: ["balance-sheet"] });
    queryClient.invalidateQueries({ queryKey: ["profit-loss"] });
  };

  const adjustments = useQuery({
    queryKey: ["supplier-adjustments", typeFilter, statusFilter],
    queryFn: () => listSupplierAdjustments({ page: 1, page_size: 100, adjustment_type: typeFilter || undefined, status: statusFilter || undefined }),
  });
  const invoices = useQuery({
    queryKey: ["posted-supplier-invoices-for-adjustment"],
    queryFn: () => listInvoices({ page: 1, page_size: 100, status: "POSTED" }),
  });
  const accounts = useQuery({
    queryKey: ["supplier-adjustment-accounts"],
    queryFn: () => getAccountLookup({ is_active: true, is_posting: true }),
  });

  const selectedInvoice = invoices.data?.items?.find((invoice: any) => invoice.id === Number(form.supplier_invoice_id));
  const create = useMutation({
    mutationFn: () => createSupplierAdjustment(form),
    onSuccess: () => {
      toast.success(form.adjustment_type === "CREDIT_NOTE" ? "Supplier credit note created" : "Supplier debit note created");
      setForm(emptyForm());
      refreshFinance();
    },
    onError: (error: any) => toast.error(error.response?.data?.detail || "Supplier adjustment could not be created"),
  });
  const action = useMutation({
    mutationFn: ({ id, name }: { id: number; name: "post" | "void" }) => supplierAdjustmentAction(id, name),
    onSuccess: (_, variables) => {
      toast.success(variables.name === "post" ? "Supplier adjustment posted" : "Supplier adjustment voided");
      refreshFinance();
    },
    onError: (error: any) => toast.error(error.response?.data?.detail || "Adjustment action failed"),
  });

  const submit = () => {
    if (!form.supplier_invoice_id) return toast.error("Select a posted supplier invoice");
    if (form.amount <= 0) return toast.error("Amount must be greater than zero");
    if (!form.adjustment_account_id) return toast.error("Select an adjustment account");
    if (!form.reason.trim()) return toast.error("Reason is required");
    create.mutate();
  };

  return <div className="space-y-6">
    <PageHeader title="Supplier Credit / Debit Notes" description="Record supplier credits or hotel-issued debit notes against posted supplier invoices without editing historical invoices." />

    <Card className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">New Supplier Adjustment</h2>
        <p className="text-sm text-slate-500">Both note types reduce the outstanding payable. Credit Note records a supplier-issued credit; Debit Note records a hotel-issued claim to the supplier.</p>
      </div>
      <div className="grid gap-3 md:grid-cols-3">
        <label className="text-sm">Document Type<select className={input} value={form.adjustment_type} onChange={(event) => setForm({ ...form, adjustment_type: event.target.value })}><option value="CREDIT_NOTE">Supplier Credit Note</option><option value="DEBIT_NOTE">Supplier Debit Note</option></select></label>
        <label className="text-sm md:col-span-2">Supplier Invoice<select className={input} value={form.supplier_invoice_id || ""} onChange={(event) => setForm({ ...form, supplier_invoice_id: Number(event.target.value) })}><option value="">Select posted invoice</option>{invoices.data?.items?.filter((invoice: any) => Number(invoice.balance_amount ?? invoice.total_amount) > 0).map((invoice: any) => <option key={invoice.id} value={invoice.id}>{invoice.internal_invoice_number} — {invoice.supplier_name} — Outstanding {money(invoice.balance_amount ?? invoice.total_amount)}</option>)}</select></label>
        <label className="text-sm">Adjustment Date<input type="date" className={input} value={form.adjustment_date} onChange={(event) => setForm({ ...form, adjustment_date: event.target.value })} /></label>
        <label className="text-sm">Amount<CurrencyInput value={Number(form.amount)} onValueChange={(value) => setForm({ ...form, amount: value })} /></label>
        <label className="text-sm">Adjustment Account<select className={input} value={form.adjustment_account_id || ""} onChange={(event) => setForm({ ...form, adjustment_account_id: Number(event.target.value) })}><option value="">Select posting account</option>{accounts.data?.map((account: any) => <option key={account.id} value={account.id}>{account.account_code} — {account.account_name}</option>)}</select></label>
        <label className="text-sm md:col-span-2">Reason<input className={input} value={form.reason} onChange={(event) => setForm({ ...form, reason: event.target.value })} placeholder="Shortage, price correction, damaged goods, rebate..." /></label>
        <label className="text-sm">Invoice Outstanding<div className="h-10 rounded-md border bg-slate-50 px-3 py-2 font-medium">{selectedInvoice ? money(selectedInvoice.balance_amount ?? selectedInvoice.total_amount) : "—"}</div></label>
        <label className="text-sm md:col-span-3">Notes<textarea className="mt-1 min-h-20 w-full rounded-md border border-slate-300 p-2 text-sm" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
      </div>
      <div className="flex justify-end"><Button loading={create.isPending} onClick={submit}>Save Draft</Button></div>
    </Card>

    <Card className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><div><h2 className="text-lg font-semibold">Supplier Adjustments</h2><p className="text-sm text-slate-500">Posted notes reduce AP and create a balanced journal automatically.</p></div><div className="flex gap-2"><select className={input} value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)}><option value="">All types</option><option value="CREDIT_NOTE">Credit Notes</option><option value="DEBIT_NOTE">Debit Notes</option></select><select className={input} value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}><option value="">All statuses</option><option value="DRAFT">Draft</option><option value="POSTED">Posted</option><option value="VOID">Void</option></select></div></div>
      <div className="overflow-x-auto"><table className="min-w-[1050px] w-full text-sm"><thead><tr><th className="text-left">Number</th><th>Type</th><th>Supplier</th><th>Invoice</th><th>Date</th><th className="text-right">Amount</th><th>Adjustment Account</th><th>Status</th><th>Actions</th></tr></thead><tbody>{adjustments.data?.items?.map((row: any) => <tr key={row.id} className="border-t"><td>{row.adjustment_number}</td><td>{row.adjustment_type === "CREDIT_NOTE" ? "Credit Note" : "Debit Note"}</td><td>{row.supplier_name}</td><td><Link className="text-emerald-700" to={`/supplier-invoices/${row.supplier_invoice_id}`}>{row.invoice_number}</Link></td><td>{row.adjustment_date}</td><td className="text-right">{money(row.amount)}</td><td>{row.adjustment_account_code} — {row.adjustment_account_name}</td><td><Badge variant={(row.status === "POSTED" ? "success" : row.status === "VOID" ? "danger" : "warning") as any}>{row.status}</Badge></td><td className="space-x-2">{row.allowed_actions?.can_post && <Button size="xs" onClick={() => action.mutate({ id: row.id, name: "post" })}>Post</Button>}{row.allowed_actions?.can_void && <Button size="xs" variant="danger" onClick={() => { if (window.confirm(`Void ${row.adjustment_number}?`)) action.mutate({ id: row.id, name: "void" }); }}>Void</Button>}{row.journal_entry_id && <Link className="text-emerald-700" to={`/journal-entries/${row.journal_entry_id}`}>Journal</Link>}</td></tr>)}</tbody></table></div>
    </Card>
  </div>;
}
