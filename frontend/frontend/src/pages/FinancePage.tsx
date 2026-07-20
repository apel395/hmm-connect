import { useQuery } from "@tanstack/react-query";

import {
  getAccountPayables,
  getAccountReceipts,
} from "../features/finance/financeApi";
import { getChartOfAccounts } from "../features/chart-of-accounts/chartOfAccountsApi";

export default function FinancePage() {
  const payablesQuery = useQuery({
    queryKey: ["account-payables"],
    queryFn: getAccountPayables,
  });

  const receiptsQuery = useQuery({
    queryKey: ["account-receipts"],
    queryFn: getAccountReceipts,
  });

  const coaQuery = useQuery({
    queryKey: ["chart-of-accounts"],
    queryFn: getChartOfAccounts,
  });

  const payables = payablesQuery.data ?? [];
  const receipts = receiptsQuery.data ?? [];
  const accounts = coaQuery.data ?? [];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">Finance</h1>
        <p className="mt-1 text-sm text-slate-500">Account payable and direct-consumption receipt records.</p>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="border-b border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900">Chart of Accounts</h2>
        </div>
        <div className="grid gap-3 p-6 sm:grid-cols-2 lg:grid-cols-5">
          {accounts.map((account) => (
            <div key={account.id} className="rounded-lg bg-slate-50 p-4">
              <p className="text-xs font-semibold text-slate-500">{account.account_number}</p>
              <p className="mt-1 text-sm font-medium text-slate-900">{account.account_name}</p>
              <p className="mt-1 text-xs text-slate-500">{account.account_type}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 p-6">
            <h2 className="font-semibold text-slate-900">Account Payable</h2>
          </div>
          {payables.length === 0 ? (
            <div className="p-8 text-sm text-slate-500">No account payable records.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead><tr className="border-b border-slate-200 text-left"><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Invoice</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">PO</th><th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Amount</th></tr></thead>
                <tbody>{payables.map((item) => <tr key={item.id} className="border-b border-slate-100 last:border-0"><td className="px-6 py-4 text-sm text-slate-700">{item.invoice_number || "—"}</td><td className="px-6 py-4 text-sm text-slate-600">{item.purchase_order_id ?? "—"}</td><td className="px-6 py-4 text-right text-sm font-medium text-slate-900">{item.amount}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </div>

        <div className="rounded-xl border border-slate-200 bg-white">
          <div className="border-b border-slate-200 p-6">
            <h2 className="font-semibold text-slate-900">Account Receipts</h2>
          </div>
          {receipts.length === 0 ? (
            <div className="p-8 text-sm text-slate-500">No direct-consumption receipts.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead><tr className="border-b border-slate-200 text-left"><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">GR</th><th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">Product</th><th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">Amount</th></tr></thead>
                <tbody>{receipts.map((item) => <tr key={item.id} className="border-b border-slate-100 last:border-0"><td className="px-6 py-4 text-sm text-slate-700">{item.goods_receipt_id}</td><td className="px-6 py-4 text-sm text-slate-600">{item.product_id}</td><td className="px-6 py-4 text-right text-sm font-medium text-slate-900">{item.total_amount}</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
