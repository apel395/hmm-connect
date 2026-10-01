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
  const [dateTo, setDateTo] = useState("");
  const query = useQuery({
    queryKey: ["financial-reconciliation", dateTo],
    queryFn: () => reconciliationApi.report({
      date_to: dateTo || undefined,
    }),
  });
  const report = query.data;

  const ledgerPath = (accountId: number) => {
    const params = new URLSearchParams({ account_id: String(accountId) });
    if (dateTo) params.set("date_to", dateTo);
    return `/journal/general-ledger?${params.toString()}`;
  };

  return <div className="space-y-6">
    <PageHeader title="Financial Reconciliation"
      description="Read-only overview by finance and inventory module. Review documents in their owning module."
      actions={<div className="flex flex-wrap gap-2">
        <Button variant="secondary" onClick={() => query.refetch()} disabled={query.isFetching}>
          <RefreshCw className="mr-2 h-4 w-4"/> Refresh
        </Button>
        <Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
      </div>}
    />
    <Card className="p-4">
      <label className="block max-w-sm text-xs font-medium text-slate-600">As of date
        <input className={input} type="date" value={dateTo}
          onChange={event => setDateTo(event.target.value)}/>
      </label>
      <p className="mt-2 text-xs text-slate-500">Leave blank for current balances. Use each module for period movement and document details.</p>
    </Card>

    {query.isError && <Card className="p-4 text-sm text-red-600">Financial reconciliation could not be loaded.</Card>}
    {query.isLoading && <Card className="p-6 text-sm text-slate-500">Loading financial reconciliation…</Card>}
    {report && <>
      <div className="grid gap-4 md:grid-cols-5">
        <Card className="p-4"><div className="text-xs text-slate-500">Reconciled</div><div className="mt-1 text-2xl font-semibold">{report.summary.reconciled}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">Out of Balance</div><div className="mt-1 text-2xl font-semibold">{report.summary.out_of_balance}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">Open Accrual Controls</div><div className="mt-1 text-2xl font-semibold">{report.summary.open_items ?? 0}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">Not Configured</div><div className="mt-1 text-2xl font-semibold">{report.summary.not_configured}</div></Card>
        <Card className="p-4"><div className="text-xs text-slate-500">History Unavailable</div><div className="mt-1 text-2xl font-semibold">{report.summary.history_unavailable ?? 0}</div></Card>
      </div>

      <Card className="p-0"><div className="overflow-x-auto">
        <table className="w-full min-w-[1080px] text-xs">
          <thead><tr>
            <th className="px-4 py-3 text-left">Module</th>
            <th className="px-4 py-3 text-left">Linked COA</th>
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
