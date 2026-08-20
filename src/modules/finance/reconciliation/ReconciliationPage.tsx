import { useQuery } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";

import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { reconciliationApi } from "./api";

const labels: Record<string, string> = {
  ACCOUNTS_PAYABLE: "Accounts Payable",
  ACCOUNTS_RECEIVABLE: "Accounts Receivable",
  INVENTORY: "Inventory Valuation",
};

const money = (value: number) =>
  new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency: "IDR",
    maximumFractionDigits: 2,
  }).format(Number(value || 0));

const statusClass: Record<string, string> = {
  RECONCILED: "bg-emerald-50 text-emerald-700",
  OUT_OF_BALANCE: "bg-red-100 text-red-700 ring-1 ring-inset ring-red-200",
  NOT_CONFIGURED: "bg-amber-50 text-amber-700",
};

export default function ReconciliationPage() {
  const query = useQuery({
    queryKey: ["financial-reconciliation"],
    queryFn: reconciliationApi.report,
  });

  const report = query.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="Financial Reconciliation"
        description="Read-only control comparing current subledger balances with posted General Ledger balances."
        actions={
          <Button variant="secondary" onClick={() => query.refetch()} disabled={query.isFetching}>
            <RefreshCw className="mr-2 h-4 w-4" />
            Refresh
          </Button>
        }
      />

      {query.isError && (
        <Card className="p-4 text-sm text-red-600">
          Financial reconciliation could not be loaded.
        </Card>
      )}

      {query.isLoading && (
        <Card className="p-6 text-sm text-slate-500">Loading financial reconciliation…</Card>
      )}

      {report && (
        <>
          <div className="grid gap-4 md:grid-cols-3">
            <Card className="p-4">
              <div className="text-xs text-slate-500">Reconciled</div>
              <div className="mt-1 text-2xl font-semibold">{report.summary.reconciled}</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-slate-500">Out of Balance</div>
              <div className="mt-1 text-2xl font-semibold">{report.summary.out_of_balance}</div>
            </Card>
            <Card className="p-4">
              <div className="text-xs text-slate-500">Not Configured</div>
              <div className="mt-1 text-2xl font-semibold">{report.summary.not_configured}</div>
            </Card>
          </div>

          <Card className="p-0">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] text-xs">
                <thead>
                  <tr>
                    <th className="px-4 py-3 text-left">Control</th>
                    <th className="px-4 py-3 text-left">Linked COA</th>
                    <th className="px-4 py-3 text-right">Source Balance</th>
                    <th className="px-4 py-3 text-right">GL Balance</th>
                    <th className="px-4 py-3 text-right">Difference</th>
                    <th className="px-4 py-3 text-left">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {report.items.map((row) => (
                    <tr key={row.control} className="border-t align-top">
                      <td className="whitespace-nowrap px-4 py-3 font-medium">
                        {labels[row.control] ?? row.control}
                      </td>
                      <td className="px-4 py-3">
                        {row.accounts.length ? (
                          <div className="space-y-1">
                            {row.accounts.map((account) => (
                              <div key={account.account_id} className="whitespace-nowrap">
                                {account.account_code} — {account.account_name}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span className="text-slate-400">Posting rule not configured</span>
                        )}
                      </td>
                      <td className="whitespace-nowrap px-4 py-3 text-right">{money(row.source_balance)}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-right">{money(row.gl_balance)}</td>
                      <td className="whitespace-nowrap px-4 py-3 text-right font-medium">{money(row.difference)}</td>
                      <td className="whitespace-nowrap px-4 py-3">
                        <span className={`inline-flex rounded-full px-2.5 py-1 font-semibold ${statusClass[row.status]}`}>
                          {row.status.replaceAll("_", " ")}
                        </span>
                      </td>
                    </tr>
                  ))}
                  {!report.items.length && (
                    <tr className="border-t">
                      <td colSpan={6} className="px-4 py-8 text-center text-slate-500">
                        No reconciliation controls were returned.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </Card>

          <p className="text-xs text-slate-500">
            Current-balance control only. This page does not create or adjust journals.
          </p>
        </>
      )}
    </div>
  );
}
