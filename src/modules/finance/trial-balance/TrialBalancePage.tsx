import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { exportTrialBalanceCsv, getTrialBalance, TrialBalanceFilters } from "./api";

const today = new Date().toISOString().slice(0, 10);
const monthStart = `${today.slice(0, 8)}01`;
const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = "h-10 rounded-md border border-slate-300 bg-white px-3 text-sm";

export default function TrialBalancePage() {
  const [draft, setDraft] = useState<TrialBalanceFilters>({ date_from: monthStart, date_to: today, page: 1, page_size: 50, search: "", include_zero_balance: false });
  const [filters, setFilters] = useState<TrialBalanceFilters>(draft);
  const query = useQuery({ queryKey: ["trial-balance", filters], queryFn: () => getTrialBalance(filters) });
  const data = query.data;
  const summary = data?.summary ?? {};

  return <div className="space-y-5">
    <PageHeader title="Trial Balance" description="Review opening, period, and closing debit/credit balances from posted ledger transactions." actions={<Button variant="outline" disabled={!data} onClick={() => exportTrialBalanceCsv(filters)}>Export CSV</Button>} />
    <Card><form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); setFilters({ ...draft, page: 1 }); }}>
      <label className="text-sm">From<input className={`${input} mt-1 w-full`} type="date" value={draft.date_from} onChange={(e) => setDraft({ ...draft, date_from: e.target.value })}/></label>
      <label className="text-sm">To<input className={`${input} mt-1 w-full`} type="date" value={draft.date_to} onChange={(e) => setDraft({ ...draft, date_to: e.target.value })}/></label>
      <label className="text-sm">Search<input className={`${input} mt-1 w-full`} placeholder="Account code or name" value={draft.search || ""} onChange={(e) => setDraft({ ...draft, search: e.target.value })}/></label>
      <div className="flex items-end gap-2"><Button type="submit">Apply</Button><label className="flex items-center gap-2 pb-2 text-sm"><input type="checkbox" checked={Boolean(draft.include_zero_balance)} onChange={(e) => setDraft({ ...draft, include_zero_balance: e.target.checked })}/>Include zero balance</label></div>
    </form></Card>

    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Metric label="Opening Debit" value={summary.opening_debit}/><Metric label="Opening Credit" value={summary.opening_credit}/><Metric label="Closing Debit" value={summary.closing_debit}/><Metric label="Closing Credit" value={summary.closing_credit}/></div>

    <Card className="overflow-x-auto p-0">{query.isLoading?<div className="p-10 text-center text-sm text-slate-500">Loading trial balance…</div>:query.isError?<div className="p-10 text-center text-sm text-red-600">Trial balance could not be loaded.</div>:<Table variant="grid"><THead><TR><TH>Account</TH><TH>Type</TH><TH className="text-right">Opening Debit</TH><TH className="text-right">Opening Credit</TH><TH className="text-right">Period Debit</TH><TH className="text-right">Period Credit</TH><TH className="text-right">Closing Debit</TH><TH className="text-right">Closing Credit</TH><TH>Status</TH></TR></THead><TBody>{data?.items.map((row)=><TR key={row.account_id}><TD><div className="font-medium">{row.account_code} — {row.account_name}</div>{row.parent_account_code&&<div className="text-xs text-slate-500">Parent: {row.parent_account_code} — {row.parent_account_name}</div>}</TD><TD>{row.account_type}</TD><TD className="text-right">{money(row.opening_debit)}</TD><TD className="text-right">{money(row.opening_credit)}</TD><TD className="text-right">{money(row.period_debit)}</TD><TD className="text-right">{money(row.period_credit)}</TD><TD className="text-right">{money(row.closing_debit)}</TD><TD className="text-right">{money(row.closing_credit)}</TD><TD>{row.is_abnormal_balance?<Badge variant="warning">Abnormal</Badge>:<Badge variant="success">Normal</Badge>}</TD></TR>)}</TBody></Table>}</Card>

    <div className="flex justify-end gap-2"><Button variant="outline" disabled={!data?.has_previous} onClick={() => setFilters({ ...filters, page: Math.max(1, Number(filters.page || 1) - 1) })}>Previous</Button><Button variant="outline" disabled={!data?.has_next} onClick={() => setFilters({ ...filters, page: Number(filters.page || 1) + 1 })}>Next</Button></div>
  </div>;
}

function Metric({ label, value }: { label: string; value: unknown }) { return <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">{label}</div><div className="mt-2 text-xl font-semibold">{money(value)}</div></Card>; }
