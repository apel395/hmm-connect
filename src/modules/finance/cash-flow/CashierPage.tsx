import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Plus } from "lucide-react";
import api from "@/api/client";
import InventoryPrintButton from "@/components/print/InventoryPrintButton";
import { collectReportPages, type ReportPage, type InventoryPrintReport } from "@/utils/inventoryPrint";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import SearchableSelect from "@/components/form/SearchableSelect";
import CurrencyInput from "@/components/form/CurrencyInput";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { listLocations, listDepartments } from "@/modules/admin/organization/api";
import useAuthStore from "@/store/auth";
import useFormRecovery from "@/hooks/useFormRecovery";
import FormRecoveryActions from "@/components/form/FormRecoveryActions";
import { todayLocal } from "@/utils/dateConstraints";

type Journal = { id: number; journal_number: string; document_type: string; posting_date: string; description: string; total_debit: string; status: string };
type CashSummary = { account_id: number; account_name: string; account_subtype: string; opening_balance: string; total_inflow: string; total_outflow: string; closing_balance: string };
const cashTypes = ["BANK", "CASH", "PETTY_CASH"];
const blank = () => ({ posting_date: todayLocal(), operation: "PAYMENT", cash_account_id: 0, counterpart_account_id: 0, amount: 0, location_id: 0, department_id: null as number | null, business_unit_id: null as number | null, reference_number: "", description: "" });
type Entry = ReturnType<typeof blank>;
const valid = (v: unknown): v is Entry => !!v && typeof v === "object" && typeof (v as Entry).posting_date === "string" && typeof (v as Entry).amount === "number";
const money = (v: unknown) => Number(v || 0).toLocaleString("id-ID", { maximumFractionDigits: 2 });
const input = "h-8 w-full rounded border px-2 text-xs";

export default function CashierPage({ petty = false }: { petty?: boolean }) {
  const canManage = useAuthStore(s => s.hasPermission("finance.manage"));
  const qc = useQueryClient();
  const [date, setDate] = useState(todayLocal);
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState(blank);
  const recovery = useFormRecovery(petty ? "petty-cash:create" : "cashier:create", form, open, valid);
  const entries = useQuery({ queryKey: ["cashier", date, page, petty], queryFn: async () => (await api.get<{ items: Journal[]; total_pages: number }>("/cashier", { params: { date_from: date, date_to: date, page, petty_cash: petty } })).data });
  const balances = useQuery({ queryKey: ["cashier-balances", date], queryFn: async () => (await api.get<CashSummary[]>("/cash-flow/accounts", { params: { date_from: date, date_to: date } })).data });
  const accounts = useQuery({ queryKey: ["cashier-accounts"], queryFn: () => getAllAccountLookup({ is_active: true, is_posting: true }), enabled: open });
  const locations = useQuery({ queryKey: ["cashier-locations"], queryFn: () => listLocations({ is_active: true }), enabled: open });
  const departments = useQuery({ queryKey: ["cashier-departments", form.location_id], queryFn: () => listDepartments({ location_id: form.location_id, is_active: true }), enabled: open && !!form.location_id });
  const cashAccounts = (accounts.data ?? []).filter(a => a.account_type === "ASSET" && cashTypes.includes(a.account_subtype || "") && (!petty || a.account_subtype === "PETTY_CASH"));
  const counterpart = (accounts.data ?? []).filter(a => a.id !== form.cash_account_id && (form.operation === "TRANSFER" ? cashTypes.includes(a.account_subtype || "") : form.operation === "PAYMENT" ? a.account_type === "EXPENSE" : ["REVENUE", "INCOME"].includes(a.account_type)));
  const options = (values: typeof cashAccounts) => values.map(a => ({ id: a.id, label: a.account_name, keywords: [a.account_code, a.account_name] }));
  const refresh = () => { ["cashier", "cashier-balances", "journal-entries", "general-ledger", "management-dashboard", "financial-report-comparison"].forEach(key => qc.invalidateQueries({ queryKey: [key] })); };
  const save = useMutation({ mutationFn: async () => (await api.post("/cashier", form)).data, onSuccess: () => { recovery.clear(); setOpen(false); setForm(blank()); refresh(); toast.success("Cashier draft saved"); }, onError: (e: { response?: { data?: { detail?: string } } }) => toast.error(e.response?.data?.detail || "Entry could not be saved") });
  const action = useMutation({ mutationFn: ({ id, name }: { id: number; name: string }) => api.post(`/cashier/${id}/${name}`), onSuccess: () => { refresh(); toast.success("Cashier entry updated"); }, onError: (e: { response?: { data?: { detail?: string } } }) => toast.error(e.response?.data?.detail || "Action failed") });
  const loadReport = async (): Promise<InventoryPrintReport> => {
    const [book, cash] = await Promise.all([collectReportPages<Journal>(async p => (await api.get<ReportPage<Journal>>("/cashier", {params: {date_from: date, date_to: date, petty_cash: petty, page: p, page_size: 100}})).data), api.get<CashSummary[]>("/cash-flow/accounts", {params: {date_from: date, date_to: date}})]);
    return {title: petty ? "Petty Cash Book" : "General Cashier Book", context: date, rowCount: book.items.length, columns: [{label: "Number"}, {label: "Date"}, {label: "Event"}, {label: "Description"}, {label: "Amount", numeric: true}, {label: "Status"}], groups: [{title: "Cashier entries", rows: book.items.map(j => [j.journal_number, j.posting_date, j.document_type.replace("CASHIER_", ""), j.description, money(j.total_debit), j.status])}, ...cash.data.filter(a => !petty || a.account_subtype === "PETTY_CASH").map(a => ({title: a.account_name, rows: [["Opening", null, null, null, money(a.opening_balance), null], ["In", null, null, null, money(a.total_inflow), null], ["Out", null, null, null, money(a.total_outflow), null], ["Closing", null, null, null, money(a.closing_balance), null]]}))]};
  };
  const summary = (balances.data ?? []).filter(a => !petty || a.account_subtype === "PETTY_CASH");
  return <div className="print-document space-y-2"><PageHeader title={petty ? "Petty Cash Usage" : "General Cashier"} description={date} actions={<><input aria-label="Cashier date" type="date" className={input} value={date} onChange={e => { setDate(e.target.value); setPage(1); }} /><InventoryPrintButton loadReport={loadReport} reportLabel={petty ? "Petty cash" : "Cashier"} />{canManage && <Button size="sm" aria-label="Create cashier draft" onClick={() => { const saved = recovery.load(); if (saved) { setForm(saved); recovery.notifyRestored(); } setOpen(true); }}><Plus size={15} /></Button>}</>} />
    {balances.isError && <p role="alert" className="text-red-700">Cash balances could not load.</p>}
    <div className="overflow-x-auto rounded border bg-white"><table className="w-full whitespace-nowrap text-xs"><thead><tr className="bg-slate-50">{["Cash account", "Opening", "In", "Out", "Closing"].map(label => <th key={label} className="px-2 py-1 text-left">{label}</th>)}</tr></thead><tbody>{summary.map(a => <tr key={a.account_id} className="border-t"><td className="px-2 py-1"><Link className="text-blue-700" to={`/cash-accounts/${a.account_id}?date_from=${date}&date_to=${date}`}>{a.account_name}</Link></td>{[a.opening_balance, a.total_inflow, a.total_outflow, a.closing_balance].map((v, i) => <td key={i} className="px-2 py-1 text-right tabular-nums">{money(v)}</td>)}</tr>)}</tbody></table></div>
    {entries.isError ? <p role="alert">Cashier entries could not load.</p> : <div className="overflow-x-auto rounded border bg-white"><table className="w-full whitespace-nowrap text-xs"><thead><tr className="bg-slate-50">{["Number", "Date", "Event", "Reference / description", "Amount", "Status", "Actions"].map(label => <th key={label} className="px-2 py-1 text-left">{label}</th>)}</tr></thead><tbody>{entries.data?.items.map(j => <tr key={j.id} className="border-t"><td className="px-2 py-1"><Link className="text-blue-700" to={`/journal-entries/${j.id}`}>{j.journal_number}</Link></td><td>{j.posting_date}</td><td>{j.document_type.replace("CASHIER_", "")}</td><td>{j.description}</td><td className="text-right">{money(j.total_debit)}</td><td>{j.status}</td><td className="flex gap-1 p-1 print:hidden">{canManage && j.status === "DRAFT" && ["post", "void"].map(name => <Button key={name} size="xs" variant="outline" disabled={action.isPending} onClick={() => { if (window.confirm(`${name === "post" ? "Post" : "Void"} ${j.journal_number}?`)) action.mutate({ id: j.id, name }); }}>{name}</Button>)}<Link className="rounded border px-2 py-1" to={`/journal-entries/${j.id}/print`}>Print</Link></td></tr>)}</tbody></table>{entries.isPending && <p className="p-2">Loading entries…</p>}</div>}
    <div className="flex gap-2 text-xs print:hidden"><Button size="xs" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><span>{page} / {entries.data?.total_pages || 1}</span><Button size="xs" disabled={page >= (entries.data?.total_pages || 1)} onClick={() => setPage(page + 1)}>Next</Button></div>
    <Dialog open={open} onOpenChange={setOpen}><DialogContent><DialogHeader><DialogTitle>{petty ? "Petty cash usage" : "Cashier entry"}</DialogTitle></DialogHeader><DialogBody><div className="grid gap-2 md:grid-cols-2">
      <label className="text-xs">Date<input className={input} type="date" value={form.posting_date} onChange={e => setForm({ ...form, posting_date: e.target.value })} /></label><label className="text-xs">Event<select className={input} value={form.operation} onChange={e => setForm({ ...form, operation: e.target.value, counterpart_account_id: 0 })}><option value="PAYMENT">Expense / payment</option>{!petty && <option value="RECEIPT">Direct revenue receipt</option>}<option value="TRANSFER">Cash / bank transfer</option></select></label>
      <SearchableSelect label="Cash account" options={options(cashAccounts)} value={form.cash_account_id || undefined} onChange={v => setForm({ ...form, cash_account_id: v || 0 })} /><SearchableSelect label={form.operation === "PAYMENT" ? "Expense account" : "Counterpart account"} options={options(counterpart)} value={form.counterpart_account_id || undefined} onChange={v => setForm({ ...form, counterpart_account_id: v || 0 })} />
      <SearchableSelect label="Location" value={form.location_id || undefined} options={(locations.data ?? []).map(l => ({ id: l.id, label: l.name }))} onChange={v => setForm({ ...form, location_id: v || 0, department_id: null, business_unit_id: locations.data?.find(l => l.id === v)?.business_unit_id ?? null })} /><SearchableSelect label="Department" options={(departments.data ?? []).map(d => ({ id: d.id, label: d.name }))} value={form.department_id || undefined} onChange={v => setForm({ ...form, department_id: v ?? null })} />
      <label className="text-xs">Amount<CurrencyInput value={form.amount} onValueChange={v => setForm({ ...form, amount: v })} /></label><label className="text-xs">Supporting document reference<input className={input} maxLength={100} value={form.reference_number} onChange={e => setForm({ ...form, reference_number: e.target.value })} /></label><label className="text-xs md:col-span-2">Description<input className={input} maxLength={500} value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} /></label>
    </div></DialogBody><DialogFooter><FormRecoveryActions failed={recovery.failed} onDiscard={() => { recovery.clear(); setForm(blank()); setOpen(false); }} /><Button variant="outline" onClick={() => setOpen(false)}>Close</Button><Button disabled={!form.location_id || !form.cash_account_id || !form.counterpart_account_id || form.amount <= 0 || !form.reference_number.trim() || !form.description.trim()} loading={save.isPending} onClick={() => save.mutate()}>Save draft</Button></DialogFooter></DialogContent></Dialog>
  </div>;
}
