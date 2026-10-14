import ReportUnitButtons from "@/components/reports/ReportUnitButtons";
import { Fragment, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ChevronRight, RefreshCw, Printer } from "lucide-react";

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
      { label: "Stock Consolidation", to: "/financial-reconciliation/stock" },
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
  const [unit,setUnit] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [expandedModule, setExpandedModule] = useState<Control | null>(null);
  const query = useQuery({
    queryKey: ["financial-reconciliation", dateTo, unit],
    queryFn: () => reconciliationApi.report({
      business_unit_id: Number(unit)||undefined,
      date_to: dateTo || undefined,
    }),
  });
  const report = query.data;

  const ledgerPath = (accountId: number) => {
    const params = new URLSearchParams({ account_id: String(accountId) });
    if (dateTo) params.set("date_to", dateTo);
    if (unit) params.set("business_unit_id",unit);
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
    <ReportUnitButtons value={unit} onChange={id=>{setUnit(id);setExpandedModule(null);}}/>
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
        <table className="w-full min-w-[920px] text-xs">
          <thead><tr>
            <th className="px-4 py-3 text-left">Module</th>
            <th className="px-4 py-3 text-right">Closing Source</th>
            <th className="px-4 py-3 text-right">Closing GL</th>
            <th className="px-4 py-3 text-right">Difference</th>
            <th className="px-4 py-3 text-left">Status</th>
            <th className="px-4 py-3 text-left">Review in module</th>
          </tr></thead>
          <tbody>{report.items.map(row => <Fragment key={row.control}>
          <tr className="border-t align-top">
            <td className="px-4 py-3 font-medium">
              <button type="button" className="inline-flex items-center gap-1.5 text-left text-blue-700 hover:underline"
                aria-expanded={expandedModule === row.control}
                aria-controls={`reconciliation-accounts-${row.control.toLowerCase()}`}
                onClick={() => setExpandedModule(expandedModule === row.control ? null : row.control)}>
                <ChevronRight size={15} className={expandedModule === row.control ? "rotate-90" : ""}/>
                {modules[row.control].label}
              </button>
            </td>
            <td className="whitespace-nowrap px-4 py-3 text-right">{row.status === "NOT_CONFIGURED" ? "Unavailable" : money(row.source_balance)}</td>
            <td className="whitespace-nowrap px-4 py-3 text-right">{money(row.gl_balance)}</td>
            <td className="whitespace-nowrap px-4 py-3 text-right font-medium">{money(row.difference)}</td>
            <td className="whitespace-nowrap px-4 py-3"><span className={`inline-flex rounded-full px-2.5 py-1 font-semibold ${statusClass[row.status]}`}>{row.status.replaceAll("_", " ")}</span></td>
            <td className="px-4 py-3"><div className="flex flex-wrap gap-x-3 gap-y-1">
              {modules[row.control].links.map(link =>
                <Link key={link.to} className="whitespace-nowrap text-blue-700 hover:underline" to={link.to}>{link.label}</Link>)}
            </div></td>
          </tr>
          {expandedModule === row.control && <tr id={`reconciliation-accounts-${row.control.toLowerCase()}`} className="border-t bg-slate-50">
            <td colSpan={6} className="px-8 py-4">
              <div className="mb-2 font-semibold text-slate-700">Linked accounts</div>
              {row.accounts.length
                ? <div className="flex flex-wrap gap-x-6 gap-y-2">
                    {row.accounts.map(account =>
                      <Link key={account.account_id} className="text-blue-700 hover:underline"
                        to={ledgerPath(account.account_id)}>
                        {account.account_code} — {account.account_name}
                      </Link>)}
                  </div>
                : <span className="text-slate-500">Posting rule not configured.</span>}
              {Boolean(row.accounts.length) && <div className="mt-5 border-t border-slate-200 pt-4">
                <div className="mb-1 font-semibold text-slate-700">Other accounts in the same posted journals</div>
                <p className="mb-3 text-xs text-slate-500">These are journal counterparts for the linked accounts above. A journal with multiple lines may appear under several accounts; these amounts are not allocated to a specific pair.</p>
                {row.counterparts?.length ? <div className="max-h-80 overflow-auto rounded border border-slate-200 bg-white">
                  <table className="w-full min-w-[740px] text-xs">
                    <thead className="sticky top-0 bg-slate-100"><tr>
                      <th className="px-3 py-2 text-left">Linked account</th>
                      <th className="px-3 py-2 text-left">Other account</th>
                      <th className="px-3 py-2 text-right">Journals</th>
                      <th className="px-3 py-2 text-right">Other debit</th>
                      <th className="px-3 py-2 text-right">Other credit</th>
                    </tr></thead>
                    <tbody>{row.counterparts.map(item => {
                      const linked = row.accounts.find(account => account.account_id === item.account_id);
                      return <tr key={`${item.account_id}-${item.counterpart_account_id}`} className="border-t">
                        <td className="px-3 py-2"><Link className="text-blue-700 hover:underline" to={ledgerPath(item.account_id)}>{linked ? `${linked.account_code} — ${linked.account_name}` : `Account #${item.account_id}`}</Link></td>
                        <td className="px-3 py-2"><Link className="text-blue-700 hover:underline" to={ledgerPath(item.counterpart_account_id)}>{item.counterpart_code} — {item.counterpart_name}</Link></td>
                        <td className="px-3 py-2 text-right">{item.journal_count}</td>
                        <td className="px-3 py-2 text-right">{money(item.counterpart_debit)}</td>
                        <td className="px-3 py-2 text-right">{money(item.counterpart_credit)}</td>
                      </tr>;
                    })}</tbody>
                  </table>
                </div> : <p className="text-xs text-slate-500">No other accounts in posted operational journals for this module.</p>}
              </div>}
              {row.control === "CLEARING_SUSPENSE" && <div className="mt-5 border-t border-slate-200 pt-4">
                <div className="mb-2 font-semibold text-slate-700">Receiving awaiting posted invoices ({row.receipt_evidence?.length ?? 0})</div>
                {row.receipt_evidence?.length ? <div className="max-h-96 overflow-auto rounded border border-slate-200 bg-white">
                  <table className="w-full min-w-[820px] text-xs">
                    <thead className="sticky top-0 bg-slate-100"><tr>
                      <th className="px-3 py-2 text-left">Receiving</th>
                      <th className="px-3 py-2 text-left">Supplier</th>
                      <th className="px-3 py-2 text-right">Received</th>
                      <th className="px-3 py-2 text-right">Invoiced at receipt cost</th>
                      <th className="px-3 py-2 text-right">Still open</th>
                      <th className="px-3 py-2 text-left">Supplier invoices</th>
                    </tr></thead>
                    <tbody>{row.receipt_evidence.map(receipt => <tr key={receipt.receipt_id} className="border-t align-top">
                      <td className="whitespace-nowrap px-3 py-2"><Link className="font-medium text-blue-700 hover:underline" to={`/receiving/${receipt.receipt_id}`}>{receipt.receipt_number}</Link><div className="text-slate-500">{receipt.date} · {receipt.items?.length ?? 0} open item(s)</div></td>
                      <td className="px-3 py-2">{receipt.supplier_name || (receipt.supplier_id ? `Supplier #${receipt.supplier_id}` : "—")}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">{money(receipt.received_amount)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right">{money(receipt.invoiced_amount)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right font-semibold">{money(receipt.outstanding_amount)}</td>
                      <td className="px-3 py-2">
                        {receipt.posted_invoices?.map(invoice => <div key={invoice.invoice_id}><Link className="text-blue-700 hover:underline" to={`/supplier-invoices/${invoice.invoice_id}`}>{invoice.invoice_number}</Link> · Posted</div>)}
                        {receipt.pending_invoices?.map(invoice => <div key={invoice.invoice_id}><Link className="text-blue-700 hover:underline" to={`/supplier-invoices/${invoice.invoice_id}`}>{invoice.invoice_number}</Link> · {invoice.status}</div>)}
                        {!receipt.posted_invoices?.length && !receipt.pending_invoices?.length && <span className="text-slate-500">No linked invoice</span>}
                      </td>
                    </tr>)}</tbody>
                  </table>
                </div> : <p className="text-slate-500">No receiving quantities awaiting a posted invoice.</p>}
                {Boolean(row.price_variance_evidence?.length) && <div className="mt-3 text-xs text-amber-800">
                  Price differences: {row.price_variance_evidence?.map(item => <span key={item.receipt_id} className="mr-3 inline-block"><Link className="underline" to={`/receiving/${item.receipt_id}`}>{item.receipt_number}</Link> {money(item.price_difference)}</span>)}
                </div>}
                {Boolean(row.match_issues?.length) && <p className="mt-2 text-xs text-red-700">{row.match_issues?.length} receiving-to-invoice link issue(s) need review.</p>}
              </div>}
            </td>
          </tr>}
          </Fragment>)}</tbody>
        </table>
      </div></Card>
      <p className="text-xs text-slate-500">This overview does not create or adjust journals. Review supporting records in each module.</p>
    </>}
  </div>;
}
