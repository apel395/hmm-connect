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
  OPEN_ITEMS: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200",
  NOT_CONFIGURED: "bg-amber-50 text-amber-700",
  HISTORY_UNAVAILABLE: "bg-amber-50 text-amber-700",
};
const input = "mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

function ApBridge({ row }: { row: ReconciliationRow }) {
  const [onlyDifferences, setOnlyDifferences] = useState(true);
  const [page, setPage] = useState(1);
  const documents = row.ap_documents ?? [];
  const filtered = onlyDifferences ? documents.filter(item => Number(item.difference) !== 0) : documents;
  const pageSize = 25;
  const pageCount = Math.max(1, Math.ceil(filtered.length / pageSize));
  const currentPage = Math.min(page, pageCount);
  const visible = filtered.slice((currentPage - 1) * pageSize, currentPage * pageSize);
  const summary = row.ap_document_summary;
  if (!documents.length) return null;
  const href = (kind: string, id: number | null) => {
    if (id == null) return null;
    if (kind === "INVOICE") return `/supplier-invoices/${id}`;
    if (kind === "PAYMENT") return `/payments/${id}`;
    if (kind === "GL_ONLY_JOURNAL") return `/journal-entries/${id}`;
    return null;
  };
  return <div className="overflow-x-auto">
    <div className="mb-2 flex flex-wrap items-center justify-between gap-3">
      <div>
        <div className="font-semibold">AP document bridge</div>
        <p className="text-xs text-slate-500">Positive amounts increase AP. Negative amounts reduce it. Opening GL has no supplier source document.</p>
      </div>
      <label className="flex items-center gap-2 text-xs text-slate-700">
        <input type="checkbox" checked={onlyDifferences} onChange={event => { setOnlyDifferences(event.target.checked); setPage(1); }}/>
        Differences only
      </label>
    </div>
    {summary && <div className="mb-2 flex flex-wrap gap-x-5 gap-y-1 rounded-md bg-white p-2 text-xs">
      <span>Invoice/payment activity: <strong>{money(summary.source_activity)}</strong></span>
      <span>GL opening: <strong>{money(summary.opening_gl)}</strong></span>
      {Number(summary.source_balance_drift) !== 0 && <span className="text-amber-800">Stored invoice balance drift: <strong>{money(summary.source_balance_drift)}</strong></span>}
      <span>Bridge difference: <strong>{money(summary.document_difference_total)}</strong></span>
    </div>}
    <table className="w-full min-w-[820px] text-left">
      <thead><tr className="border-b text-slate-500">
        <th className="py-2">Date</th><th className="py-2">Document</th><th className="py-2">Type</th>
        <th className="py-2">Supplier ID</th><th className="py-2 text-right">Source activity</th>
        <th className="py-2 text-right">Posted AP GL</th><th className="py-2 text-right">Impact</th>
      </tr></thead>
      <tbody>{visible.map((item, index) => <tr key={`${item.kind}-${item.document_id ?? index}`} className="border-b">
        <td className="py-2">{item.date ?? "—"}</td>
        <td className="py-2 font-medium">
          {href(item.kind, item.document_id)
            ? <Link className="text-blue-700 hover:underline" to={href(item.kind, item.document_id)!}>{item.document_number}</Link>
            : item.document_number}
          {item.journal_ids.length > 0 && <div className="text-xs font-normal text-slate-500">
            {item.journal_ids.map(id => <Link key={id} className="mr-2 text-blue-700 hover:underline" to={`/journal-entries/${id}`}>Journal #{id}</Link>)}
          </div>}
        </td>
        <td className="py-2">{item.kind.replaceAll("_", " ")}</td>
        <td className="py-2">{item.supplier_id ?? "—"}</td>
        <td className="py-2 text-right">{money(item.source_amount)}</td>
        <td className="py-2 text-right">{money(item.gl_amount)}</td>
        <td className={`py-2 text-right font-medium ${Number(item.difference) !== 0 ? "text-red-700" : "text-emerald-700"}`}>{money(item.difference)}</td>
      </tr>)}</tbody>
    </table>
    {!filtered.length && <p className="py-3 text-xs text-slate-500">No document differences in this selection.</p>}
    {filtered.length > pageSize && <div className="mt-2 flex items-center justify-between text-xs">
      <span>{filtered.length} records · page {currentPage} of {pageCount}</span>
      <div className="flex gap-2">
        <button type="button" className="rounded border px-2 py-1 disabled:opacity-40" disabled={currentPage <= 1} onClick={() => setPage(currentPage - 1)}>Previous</button>
        <button type="button" className="rounded border px-2 py-1 disabled:opacity-40" disabled={currentPage >= pageCount} onClick={() => setPage(currentPage + 1)}>Next</button>
      </div>
    </div>}
  </div>;
}

function ReceiptEvidence({ row }: { row: ReconciliationRow }) {
  const receipts = row.receipt_evidence ?? [];
  if (!receipts.length) return null;
  return <div className="overflow-x-auto">
    <div className="mb-2 font-semibold">Open receiving accrual by document</div>
    <table className="w-full min-w-[760px] text-left">
      <thead><tr className="border-b text-slate-500">
        <th className="py-2">Received</th><th className="py-2">Receipt</th><th className="py-2">Supplier ID</th>
        <th className="py-2 text-right">Receipt value</th><th className="py-2 text-right">Posted invoice lines</th>
        <th className="py-2 text-right">Still open</th>
      </tr></thead>
      <tbody>{receipts.map(item => <tr key={item.receipt_id} className="border-b">
        <td className="py-2">{item.date}</td>
        <td className="py-2"><Link className="font-medium text-blue-700 hover:underline" to={`/receiving/${item.receipt_id}`}>{item.receipt_number}</Link>
          {!!item.invoice_numbers.length && <div className="text-xs text-slate-500">{item.invoice_numbers.join(", ")}</div>}
        </td>
        <td className="py-2">{item.supplier_id ?? "—"}</td>
        <td className="py-2 text-right">{money(item.received_amount)}</td>
        <td className="py-2 text-right">{money(item.invoiced_amount)}</td>
        <td className="py-2 text-right font-medium">{money(item.outstanding_amount)}</td>
      </tr>)}</tbody>
    </table>
  </div>;
}

function Evidence({ row }: { row: ReconciliationRow }) {
  const detail = row.detail ?? [];
  const exceptions = row.exceptions ?? [];
  const counterparts = row.counterparts ?? [];
  if (!detail.length && !counterparts.length && !exceptions.length && !row.note &&
      !row.ap_documents?.length && !row.receipt_evidence?.length) {
    return <p className="text-sm text-slate-500">No document detail is available for this control.</p>;
  }
  return <div className="space-y-4 text-sm">
    {row.note && <p className="rounded-md bg-amber-50 p-3 text-amber-800">{row.note}</p>}
    {row.control === "ACCOUNTS_PAYABLE" && <ApBridge row={row}/>}
    {row.control === "CLEARING_SUSPENSE" && <ReceiptEvidence row={row}/>}
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
    {!!counterparts.length && <div className="overflow-x-auto">
      <div className="mb-2 font-semibold">Opposing accounts in posted journals</div>
      <table className="w-full min-w-[720px] text-left">
        <thead><tr className="border-b text-slate-500">
          <th className="py-2">Control COA</th><th className="py-2">Other COA</th>
          <th className="py-2 text-right">Journals</th>
          <th className="py-2 text-right">Other debit</th><th className="py-2 text-right">Other credit</th>
        </tr></thead>
        <tbody>{counterparts.map(entry => <tr key={`${entry.account_id}-${entry.counterpart_account_id}`} className="border-b">
          <td className="py-2">{row.accounts.find(account => account.account_id === entry.account_id)?.account_code ?? entry.account_id}</td>
          <td className="py-2">{entry.counterpart_code} — {entry.counterpart_name}</td>
          <td className="py-2 text-right">{entry.journal_count}</td>
          <td className="py-2 text-right">{money(entry.counterpart_debit)}</td>
          <td className="py-2 text-right">{money(entry.counterpart_credit)}</td>
        </tr>)}</tbody>
      </table>
      <p className="mt-2 text-xs text-slate-500">These accounts occur in the same posted journals. A journal can contain several lines, so the amounts are not allocated to one control account.</p>
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
      <div className="grid gap-4 md:grid-cols-5">
        <Card className="p-4"><div className="text-xs text-slate-500">Reconciled</div><div className="mt-1 text-2xl font-semibold">{report.summary.reconciled}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">Out of Balance</div><div className="mt-1 text-2xl font-semibold">{report.summary.out_of_balance}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">Open Receipt Accruals</div><div className="mt-1 text-2xl font-semibold">{report.summary.open_items ?? 0}</div></Card>
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
