import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { RefreshCw, Printer } from "lucide-react";

import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { reconciliationApi, type ReconciliationRow } from "./api";

type Control = ReconciliationRow["control"];

const modules: Record<Control, {
  label: string;
  links: { label: string; to: string }[];
}> = {
  ACCOUNTS_PAYABLE: {
    label: "Accounts Payable",
    links: [
      { label: "AP Movement", to: "/accounts-payable/movement" },
      { label: "Supplier Invoices", to: "/supplier-invoices" },
      { label: "Payments", to: "/payments" },
    ],
  },
  ACCOUNTS_RECEIVABLE: {
    label: "Accounts Receivable",
    links: [{ label: "Accounts Receivable", to: "/accounts-receivable" }],
  },
  CLEARING_SUSPENSE: {
    label: "AP Suspense",
    links: [
      { label: "Receiving", to: "/receiving" },
      { label: "Supplier Invoices", to: "/supplier-invoices" },
    ],
  },
  INVENTORY: {
    label: "Inventory",
    links: [
      { label: "Stock", to: "/inventory" },
      { label: "Stock Movements", to: "/inventory/movements" },
    ],
  },
};

const money = (value: number | null | undefined) =>
  value == null ? "Unavailable" : new Intl.NumberFormat("id-ID", {
    style: "currency", currency: "IDR", maximumFractionDigits: 2,
  }).format(Number(value));

const statusClass: Record<ReconciliationRow["status"], string> = {
  RECONCILED: "bg-emerald-50 text-emerald-700",
  OUT_OF_BALANCE: "bg-red-100 text-red-700 ring-1 ring-inset ring-red-200",
  OPEN_ITEMS: "bg-amber-50 text-amber-700 ring-1 ring-inset ring-amber-200",
  NOT_CONFIGURED: "bg-amber-50 text-amber-700",
  HISTORY_UNAVAILABLE: "bg-amber-50 text-amber-700",
};

const input = "mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

export default function ReconciliationPage() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const invalidRange = Boolean(dateFrom && dateTo && dateFrom > dateTo);
  const query = useQuery({
    queryKey: ["financial-reconciliation", dateFrom, dateTo],
    queryFn: () => reconciliationApi.report({
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    }),
    enabled: !invalidRange,
  });
  const report = query.data;

  const ledgerPath = (accountId: number) => {
    const params = new URLSearchParams({ account_id: String(accountId) });
    if (dateFrom) params.set("date_from", dateFrom);
    if (dateTo) params.set("date_to", dateTo);
    return `/journal/general-ledger?${params.toString()}`;
  };

  return <div className="space-y-6">
    <PageHeader title="Financial Reconciliation"
      description="Read-only overview by finance and inventory module. Review documents in their owning module."
      actions={<div className="flex flex-wrap gap-2">
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
            onChange={event => setDateFrom(event.target.value)}/>
        </label>
        <label className="text-xs font-medium text-slate-600">To date
          <input className={input} type="date" value={dateTo} min={dateFrom || undefined}
            onChange={event => setDateTo(event.target.value)}/>
        </label>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        {dateFrom
          ? `Balances before ${dateFrom}, movement through ${dateTo || "today"}, and closing balances.`
          : `Closing balances ${dateTo ? `through ${dateTo}` : "as of today"}. Add From date to show movement.`}
      </p>
      {invalidRange && <p className="mt-2 text-sm text-red-700">From date must be on or before To date.</p>}
    </Card>

    {query.isError && <Card className="p-4 text-sm text-red-600">Financial reconciliation could not be loaded.</Card>}
    {query.isLoading && <Card className="p-6 text-sm text-slate-500">Loading financial reconciliation…</Card>}
    {!invalidRange && report && <>
      <div className="grid gap-4 md:grid-cols-5">
        <Card className="p-4"><div className="text-xs text-slate-500">Reconciled</div><div className="mt-1 text-2xl font-semibold">{report.summary.reconciled}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">Out of Balance</div><div className="mt-1 text-2xl font-semibold">{report.summary.out_of_balance}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">Open Accrual Controls</div><div className="mt-1 text-2xl font-semibold">{report.summary.open_items ?? 0}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">Not Configured</div><div className="mt-1 text-2xl font-semibold">{report.summary.not_configured}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">History Unavailable</div><div className="mt-1 text-2xl font-semibold">{report.summary.history_unavailable ?? 0}</div></Card>
      </div>

      <Card className="p-0"><div className="overflow-x-auto">
        <table className={`w-full text-xs ${dateFrom ? "min-w-[1500px]" : "min-w-[1080px]"}`}>
          <thead><tr>
            <th className="px-4 py-3 text-left">Module</th>
            <th className="px-4 py-3 text-left">Linked COA</th>
            {dateFrom && <th className="px-4 py-3 text-right">Before: Source</th>}
            {dateFrom && <th className="px-4 py-3 text-right">Before: GL</th>}
            {dateFrom && <th className="px-4 py-3 text-right">Movement: Source</th>}
            {dateFrom && <th className="px-4 py-3 text-right">Movement: GL</th>}
            <th className="px-4 py-3 text-right">Closing Source</th>
            <th className="px-4 py-3 text-right">Closing GL</th>
            <th className="px-4 py-3 text-right">Difference</th>
            <th className="px-4 py-3 text-left">Status</th>
            <th className="px-4 py-3 text-left">Review in module</th>
          </tr></thead>
          <tbody>{report.items.map(row => <tr key={row.control} className="border-t align-top">
            <td className="px-4 py-3 font-medium">{modules[row.control].label}</td>
            <td className="px-4 py-3">{row.accounts.length
              ? row.accounts.map(account => <div key={account.account_id} className="whitespace-nowrap">
                  <Link className="text-blue-700 hover:underline" to={ledgerPath(account.account_id)}>
                    {account.account_code} — {account.account_name}
                  </Link>
                </div>)
              : <span className="text-slate-400">Posting rule not configured</span>}
            </td>
            {dateFrom && <td className="whitespace-nowrap px-4 py-3 text-right">{money(row.period?.opening_source)}</td>}
            {dateFrom && <td className="whitespace-nowrap px-4 py-3 text-right">{money(row.period?.opening_gl)}</td>}
            {dateFrom && <td className="whitespace-nowrap px-4 py-3 text-right">{money(row.period?.source_change)}</td>}
            {dateFrom && <td className="whitespace-nowrap px-4 py-3 text-right">{money(row.period?.gl_change)}</td>}
            <td className="whitespace-nowrap px-4 py-3 text-right">{row.status === "NOT_CONFIGURED" ? "Unavailable" : money(row.source_balance)}</td>
            <td className="whitespace-nowrap px-4 py-3 text-right">{money(row.gl_balance)}</td>
            <td className="whitespace-nowrap px-4 py-3 text-right font-medium">{money(row.difference)}</td>
            <td className="whitespace-nowrap px-4 py-3"><span className={`inline-flex rounded-full px-2.5 py-1 font-semibold ${statusClass[row.status]}`}>{row.status.replaceAll("_", " ")}</span></td>
            <td className="px-4 py-3"><div className="flex flex-wrap gap-x-3 gap-y-1">
              {modules[row.control].links.map(link =>
                <Link key={link.to} className="whitespace-nowrap text-blue-700 hover:underline" to={link.to}>{link.label}</Link>)}
            </div></td>
          </tr>)}</tbody>
        </table>
      </div></Card>
      <p className="text-xs text-slate-500">This overview does not create or adjust journals. Review supporting records in each module.</p>
    </>}
  </div>;
}
