import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RefreshCw, Printer } from "lucide-react";

import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { reconciliationApi, type ReconciliationRow } from "./api";

const labels: Record<string, string> = {
  ACCOUNTS_PAYABLE: "Accounts Payable",
  ACCOUNTS_RECEIVABLE: "Accounts Receivable",
  INVENTORY: "Inventory Valuation",
  CLEARING_SUSPENSE: "Clearing / Suspense",
};

const money = (value: number | null | undefined) =>
  value == null ? "Unavailable" : new Intl.NumberFormat("id-ID", {
    style: "currency", currency: "IDR", maximumFractionDigits: 2,
  }).format(Number(value));

const statusClass: Record<string, string> = {
  RECONCILED: "bg-emerald-50 text-emerald-700",
  OUT_OF_BALANCE: "bg-red-100 text-red-700 ring-1 ring-inset ring-red-200",
  NOT_CONFIGURED: "bg-amber-50 text-amber-700",
  HISTORY_UNAVAILABLE: "bg-amber-50 text-amber-700",
};
const input = "mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

function Evidence({ row }: { row: ReconciliationRow }) {
  const detail = row.detail ?? [];
  const exceptions = row.exceptions ?? [];
  if (!detail.length && !exceptions.length && !row.note) {
    return <p className="text-sm text-slate-500">No document detail is available for this control.</p>;
  }
  return <div className="space-y-4 text-sm">
    {row.note && <p className="rounded-md bg-amber-50 p-3 text-amber-800">{row.note}</p>}
    {!!detail.length && <div className="overflow-x-auto">
      <div className="mb-2 font-semibold">Balances by account</div>
      <table className="w-full min-w-[620px] text-left">
        <thead><tr className="border-b text-slate-500">
          <th className="py-2">Account</th><th className="py-2 text-right">Stock / Source</th>
          <th className="py-2 text-right">Posted GL</th><th className="py-2 text-right">Difference</th>
        </tr></thead>
        <tbody>{detail.map((entry, index) => <tr key={entry.account_id ?? index} className="border-b">
          <td className="py-2">{entry.account_code} — {entry.account_name}</td>
          <td className="py-2 text-right">{money(entry.source_balance)}</td>
          <td className="py-2 text-right">{money(entry.gl_balance)}</td>
          <td className="py-2 text-right">{money(entry.variance)}</td>
        </tr>)}</tbody>
      </table>
      {row.control === "INVENTORY" &&
        <p className="mt-2 text-xs text-slate-500">Stock source uses inventory quantity × average cost. Movement values are a separate diagnostic and exclude manually entered opening stock.</p>}
    </div>}
    {!!exceptions.length && <div className="overflow-x-auto">
      <div className="mb-2 font-semibold">
        {row.control === "ACCOUNTS_PAYABLE" ? "Posted payments requiring allocation review" : "Recent suspense journal lines"}
      </div>
      <table className="w-full min-w-[660px] text-left">
        <thead><tr className="border-b text-slate-500">
          <th className="py-2">Date</th><th className="py-2">Document</th>
          <th className="py-2">Supplier ID</th><th className="py-2">Source</th>
          <th className="py-2 text-right">Amount</th>
        </tr></thead>
        <tbody>{exceptions.map((item, index) => <tr key={`${item.kind}-${item.document_id}-${index}`} className="border-b">
          <td className="py-2">{item.date}</td>
          <td className="py-2 font-medium">{item.document_number}</td>
          <td className="py-2">{item.supplier_id ?? "—"}</td>
          <td className="py-2">{item.kind === "UNALLOCATED_PAYMENT"
            ? "Payment with unallocated amount"
            : `${item.reference_type ?? "Journal"} #${item.reference_id ?? item.document_id}`}</td>
          <td className="py-2 text-right">{money(item.amount)}</td>
        </tr>)}</tbody>
      </table>
      {row.control === "CLEARING_SUSPENSE" && <p className="mt-2 text-xs text-slate-500">Showing up to 100 recent lines. Positive amounts are credits; negative amounts are debits.</p>}
      {row.control === "ACCOUNTS_PAYABLE" && <p className="mt-2 text-xs text-slate-500">An unallocated payment is an investigation lead, not automatically the full cause of the AP difference.</p>}
    </div>}
  </div>;
}

export default function ReconciliationPage() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const invalidRange = Boolean(dateFrom && dateTo && dateFrom > dateTo);
  const query = useQuery({
    queryKey: ["financial-reconciliation", dateFrom, dateTo],
    queryFn: () => reconciliationApi.report({
      date_from: dateFrom || undefined, date_to: dateTo || undefined,
    }),
    enabled: !invalidRange,
  });
  const report = query.data;

  return <div className="space-y-6">
    <PageHeader title="Financial Reconciliation"
      description="Read-only comparison of subledger and posted General Ledger balances."
      actions={<div className="flex flex-wrap gap-2">
        <Link className="inline-flex h-9 items-center rounded-md border px-3 text-sm font-medium" to="/financial-reconciliation/stock">Stock Consolidation</Link>
        <Button variant="secondary" onClick={() => query.refetch()} disabled={query.isFetching || invalidRange}>
          <RefreshCw className="mr-2 h-4 w-4"/> Refresh
        </Button>
        <Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
      </div>}
    />
    <Card className="p-4">
      <div className="grid gap-4 sm:grid-cols-2">
        <label className="text-xs font-medium text-slate-600">From date
          <input className={input} type="date" value={dateFrom} max={dateTo || undefined}
            onChange={e => setDateFrom(e.target.value)}/>
        </label>
        <label className="text-xs font-medium text-slate-600">To date
          <input className={input} type="date" value={dateTo} min={dateFrom || undefined}
            onChange={e => setDateTo(e.target.value)}/>
        </label>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {dateFrom
          ? `Opening before ${dateFrom}; closing ${dateTo || "current balance"}. Period change is closing minus opening.`
          : `Closing ${dateTo || "current balance"}. Add From date to show opening and period change.`}
      </p>
      {invalidRange && <p className="mt-2 text-sm text-red-700">From date must be on or before To date.</p>}
    </Card>

    {query.isError && <Card className="p-4 text-sm text-red-600">Financial reconciliation could not be loaded.</Card>}
    {query.isLoading && <Card className="p-6 text-sm text-slate-500">Loading financial reconciliation…</Card>}
    {!invalidRange && report && <>
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="p-4"><div className="text-xs text-slate-500">Reconciled</div><div className="mt-1 text-2xl font-semibold">{report.summary.reconciled}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">Out of Balance</div><div className="mt-1 text-2xl font-semibold">{report.summary.out_of_balance}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">Not Configured</div><div className="mt-1 text-2xl font-semibold">{report.summary.not_configured}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">History Unavailable</div><div className="mt-1 text-2xl font-semibold">{report.summary.history_unavailable ?? 0}</div></Card>
      </div>

      <Card className="p-0"><div className="overflow-x-auto">
        <table className="w-full min-w-[1060px] text-xs">
          <thead><tr>
            <th className="px-4 py-3 text-left">Control</th>
            <th className="px-4 py-3 text-left">Linked COA</th>
            {dateFrom && <th className="px-4 py-3 text-right">Opening Source</th>}
            <th className="px-4 py-3 text-right">Closing Source</th>
            <th className="px-4 py-3 text-right">Closing GL</th>
            {dateFrom && <th className="px-4 py-3 text-right">Period Source Change</th>}
            <th className="px-4 py-3 text-right">Difference</th>
            <th className="px-4 py-3 text-left">Status</th>
          </tr></thead>
          <tbody>{report.items.map(row => <tr key={row.control} className="border-t align-top">
            <td className="px-4 py-3 font-medium">
              <div className="whitespace-nowrap">{labels[row.control] ?? row.control}</div>
              <details className="mt-2 w-[760px] max-w-[70vw] print:w-auto">
                <summary className="cursor-pointer text-xs font-medium text-blue-700">View accounts & documents</summary>
                <div className="mt-3 rounded-md border bg-slate-50 p-3"><Evidence row={row}/></div>
              </details>
            </td>
            <td className="px-4 py-3">{row.accounts.length
              ? row.accounts.map(account => <div key={account.account_id} className="whitespace-nowrap">{account.account_code} — {account.account_name}</div>)
              : <span className="text-slate-400">Posting rule not configured</span>}
            </td>
            {dateFrom && <td className="whitespace-nowrap px-4 py-3 text-right">{money(row.period?.opening_source)}</td>}
            <td className="whitespace-nowrap px-4 py-3 text-right">{row.status === "NOT_CONFIGURED" ? "Unavailable" : money(row.source_balance)}</td>
            <td className="whitespace-nowrap px-4 py-3 text-right">{money(row.gl_balance)}</td>
            {dateFrom && <td className="whitespace-nowrap px-4 py-3 text-right">{money(row.period?.source_change)}</td>}
            <td className="whitespace-nowrap px-4 py-3 text-right font-medium">{money(row.difference)}</td>
            <td className="whitespace-nowrap px-4 py-3"><span className={`inline-flex rounded-full px-2.5 py-1 font-semibold ${statusClass[row.status]}`}>{row.status.replaceAll("_", " ")}</span></td>
          </tr>)}</tbody>
        </table>
      </div></Card>
      <p className="text-xs text-slate-500">This page does not create or adjust journals. Review document evidence before resolving a variance.</p>
    </>}
  </div>;
}
