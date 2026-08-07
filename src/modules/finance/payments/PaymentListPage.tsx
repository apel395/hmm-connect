import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import { listBankAccounts } from "@/modules/finance/cash-flow/bankAccountApi";
import { createPayment, eligibleInvoices, listPayments } from "./api";

const methods = ["BANK_TRANSFER", "CASH", "CHEQUE", "CREDIT_CARD", "PETTY_CASH", "OTHER"];
const today = () => new Date().toISOString().slice(0, 10);
const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

const emptyForm = () => ({
  supplier_id: 0,
  payment_date: today(),
  payment_method: "BANK_TRANSFER",
  currency: "IDR",
  total_amount: 0,
  reference_number: "",
  cheque_number: "",
  notes: "",
  source_type: "LIVE",
  allocations: [] as any[],
  funding_lines: [{ bank_account_id: 0, amount: 0 }] as any[],
});

export default function PaymentListPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<any>(emptyForm());

  const payments = useQuery({ queryKey: ["payments", page, search, status], queryFn: () => listPayments({ page, page_size: 20, search: search || undefined, status: status || undefined }) });
  const { data: suppliers = [] } = useSuppliers();
  const bankAccounts = useQuery({ queryKey: ["active-bank-accounts"], queryFn: () => listBankAccounts(true) });
  const invoices = useQuery({ queryKey: ["eligible-payment-invoices", form.supplier_id, form.currency], queryFn: () => eligibleInvoices(form.supplier_id, form.currency), enabled: Boolean(form.supplier_id) });

  useEffect(() => {
    setForm((current: any) => ({ ...current, allocations: [] }));
  }, [form.supplier_id]);

  const allocated = useMemo(() => form.allocations.reduce((sum: number, row: any) => sum + Number(row.allocated_amount || 0), 0), [form.allocations]);
  const funded = useMemo(() => form.funding_lines.reduce((sum: number, row: any) => sum + Number(row.amount || 0), 0), [form.funding_lines]);

  const setAllocation = (invoiceId: number, amount: number) => setForm((current: any) => ({
    ...current,
    allocations: amount > 0
      ? [...current.allocations.filter((row: any) => row.supplier_invoice_id !== invoiceId), { supplier_invoice_id: invoiceId, allocated_amount: amount }]
      : current.allocations.filter((row: any) => row.supplier_invoice_id !== invoiceId),
  }));
  const setFunding = (index: number, patch: any) => setForm((current: any) => ({ ...current, funding_lines: current.funding_lines.map((row: any, rowIndex: number) => rowIndex === index ? { ...row, ...patch } : row) }));

  const save = useMutation({
    mutationFn: () => createPayment({ ...form, total_amount: allocated }),
    onSuccess: (payment) => {
      toast.success("Payment saved as draft");
      setOpen(false);
      setForm(emptyForm());
      queryClient.invalidateQueries({ queryKey: ["payments"] });
      navigate(`/payments/${payment.id}`);
    },
    onError: (error: any) => toast.error(error.response?.data?.detail || "Payment could not be saved"),
  });

  const submit = () => {
    if (!form.supplier_id) return toast.error("Select a supplier");
    if (!form.allocations.length || allocated <= 0) return toast.error("Allocate at least one supplier invoice");
    if (funded !== allocated) return toast.error("Funding total must equal invoice allocations");
    if (form.funding_lines.some((row: any) => !row.bank_account_id || row.amount <= 0)) return toast.error("Complete every funding line");
    save.mutate();
  };

  return <>
    <PageHeader title="Payments" description="Allocate supplier invoices and fund one payment from one or more registered bank accounts." actions={<Button onClick={() => setOpen(true)}>Create Payment</Button>} />
    <Card>
      <div className="mb-4 grid gap-3 md:grid-cols-2"><input className={input} placeholder="Search payments" value={search} onChange={(event) => setSearch(event.target.value)} /><select className={input} value={status} onChange={(event) => setStatus(event.target.value)}><option value="">All statuses</option>{["DRAFT", "APPROVED", "POSTED", "VOID"].map((value) => <option key={value}>{value}</option>)}</select></div>
      <div className="overflow-x-auto"><table className="min-w-[1000px] w-full text-sm"><thead><tr><th>Payment Number</th><th>Date</th><th>Supplier</th><th>Method</th><th>Amount</th><th>Allocated</th><th>Funded</th><th>Status</th><th>Action</th></tr></thead><tbody>{payments.data?.items.map((row: any) => <tr key={row.id} className="border-t"><td>{row.payment_number}</td><td>{row.payment_date}</td><td>{row.supplier_name}</td><td>{row.payment_method}</td><td>{money(row.total_amount)}</td><td>{money(row.allocated_amount)}</td><td>{money(row.funded_amount)}</td><td>{row.status}</td><td><Button size="xs" variant="outline" onClick={() => navigate(`/payments/${row.id}`)}>View</Button></td></tr>)}</tbody></table></div>
      <div className="mt-4 flex justify-end gap-2"><Button variant="outline" disabled={!payments.data?.has_previous} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" disabled={!payments.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button></div>
    </Card>

    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-6xl"><DialogHeader><DialogTitle>Create Supplier Payment</DialogTitle></DialogHeader><DialogBody className="space-y-6">
      <div className="grid gap-3 md:grid-cols-4">
        <label className="text-sm">Supplier<select required className={input} value={form.supplier_id} onChange={(event) => setForm({ ...form, supplier_id: Number(event.target.value) })}><option value={0}>Select supplier</option>{suppliers.map((supplier: any) => <option key={supplier.id} value={supplier.id}>{supplier.code} — {supplier.name}</option>)}</select></label>
        <label className="text-sm">Payment Date<input type="date" className={input} value={form.payment_date} onChange={(event) => setForm({ ...form, payment_date: event.target.value })} /></label>
        <label className="text-sm">Payment Method<select className={input} value={form.payment_method} onChange={(event) => setForm({ ...form, payment_method: event.target.value })}>{methods.map((value) => <option key={value}>{value}</option>)}</select></label>
        <label className="text-sm">Currency<input className={input} value={form.currency} maxLength={3} onChange={(event) => setForm({ ...form, currency: event.target.value.toUpperCase() })} /></label>
        <label className="text-sm md:col-span-2">Reference Number<input className={input} value={form.reference_number} onChange={(event) => setForm({ ...form, reference_number: event.target.value })} /></label>
        {form.payment_method === "CHEQUE" && <label className="text-sm">Cheque Number<input className={input} value={form.cheque_number} onChange={(event) => setForm({ ...form, cheque_number: event.target.value })} /></label>}
      </div>

      <section><div className="mb-2"><h3 className="font-semibold">Invoice Allocations</h3><p className="text-sm text-slate-500">Select one or more outstanding invoices from the same supplier.</p></div><div className="overflow-x-auto rounded border"><table className="min-w-[900px] w-full text-sm"><thead><tr><th>Invoice</th><th>Date</th><th>Due</th><th>Total</th><th>Paid</th><th>Outstanding</th><th>Allocate</th></tr></thead><tbody>{invoices.data?.map((row: any) => { const current = form.allocations.find((allocation: any) => allocation.supplier_invoice_id === row.id)?.allocated_amount ?? 0; return <tr key={row.id} className="border-t"><td>{row.invoice_number}</td><td>{row.invoice_date}</td><td>{row.due_date || "—"}</td><td>{money(row.total_amount)}</td><td>{money(row.paid_amount)}</td><td>{money(row.outstanding_balance)}</td><td className="w-44"><CurrencyInput value={Number(current)} onValueChange={(value) => setAllocation(row.id, Math.min(value, Number(row.outstanding_balance)))} /></td></tr>; })}</tbody></table></div></section>

      <section className="space-y-3"><div><h3 className="font-semibold">Funding Accounts</h3><p className="text-sm text-slate-500">A payment may be split across multiple registered bank accounts. The linked COA is used automatically.</p></div>{form.funding_lines.map((row: any, index: number) => <div key={index} className="grid gap-3 rounded border p-3 md:grid-cols-[1fr_220px_auto]"><select className={input} value={row.bank_account_id || ""} onChange={(event) => setFunding(index, { bank_account_id: Number(event.target.value) })}><option value="">Select bank account</option>{bankAccounts.data?.filter((bank) => bank.currency === form.currency).map((bank) => <option key={bank.id} value={bank.id}>{bank.bank_name} — {bank.account_name} — {bank.account_number}</option>)}</select><CurrencyInput value={Number(row.amount || 0)} onValueChange={(value) => setFunding(index, { amount: value })} /><Button variant="outline" disabled={form.funding_lines.length === 1} onClick={() => setForm({ ...form, funding_lines: form.funding_lines.filter((_: any, rowIndex: number) => rowIndex !== index) })}>Remove</Button></div>)}<Button variant="outline" onClick={() => setForm({ ...form, funding_lines: [...form.funding_lines, { bank_account_id: 0, amount: 0 }] })}>Add Funding Account</Button></section>

      <div className="grid gap-3 rounded bg-slate-50 p-4 text-right md:grid-cols-3"><div>Invoice Allocations<br/><strong>{money(allocated)}</strong></div><div>Funding Total<br/><strong>{money(funded)}</strong></div><div>Difference<br/><strong>{money(funded - allocated)}</strong></div></div>
      <label className="block text-sm">Notes<textarea className="mt-1 min-h-20 w-full rounded border p-2" value={form.notes} onChange={(event) => setForm({ ...form, notes: event.target.value })} /></label>
    </DialogBody><DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button loading={save.isPending} onClick={submit}>Save Draft</Button></DialogFooter></DialogContent></Dialog>
  </>;
}
