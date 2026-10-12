import PurchasingExceptionPanel from "./PurchasingExceptionPanel";
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import { Printer } from "lucide-react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import Badge from "@/components/ui/Badge";
import useAuthStore from "@/store/auth";
import { canAccess } from "@/lib/access";
import ForbiddenPage from "@/pages/errors/ForbiddenPage";
import { purchasingReportsApi } from "./api";

const PURCHASING_REPORT_ROLES = ["SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];
const money = (v: unknown) => "Rp " + Number(v ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (v: unknown) => Number(v ?? 0).toLocaleString("id-ID");
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const today = () => new Date().toISOString().slice(0, 10);
const monthStart = () => new Date(new Date().getFullYear(), new Date().getMonth(), 1).toISOString().slice(0, 10);

function statusBadge(status: string): { label: string; variant: "default" | "warning" | "success" | "primary" | "info" | "outline" | "danger" | "secondary" } {
  switch (status) {
    case "APPROVED": return { label: "Approved", variant: "primary" };
    case "OPEN": return { label: "Open", variant: "warning" };
    case "RECEIVED": return { label: "Received", variant: "success" };
    case "POSTED": return { label: "Posted", variant: "success" };
    case "PARTIALLY_RECEIVED": return { label: "Partially Received", variant: "info" };
    case "DRAFT": return { label: "Draft", variant: "secondary" };
    case "SUBMITTED": return { label: "Submitted", variant: "info" };
    case "COMPLETED": return { label: "Completed", variant: "success" };
    case "CLOSED": return { label: "Closed", variant: "default" };
    case "CANCELLED": case "REJECTED": return { label: status[0] + status.slice(1).toLowerCase(), variant: "danger" };
    default: return { label: status.replaceAll("_", " "), variant: "default" };
  }
}

export default function PurchasingReportsPage() {
  const user = useAuthStore((state) => state.user);
  const [dateFrom, setDateFrom] = useState(monthStart());
  const [dateTo, setDateTo] = useState(today());
  const [historySearch, setHistorySearch] = useState("");
  const [historyPage, setHistoryPage] = useState(1);
  const invalidRange = Boolean(dateFrom && dateTo && dateFrom > dateTo);

  const query = useQuery({
    queryKey: ["purchasing-report", dateFrom, dateTo],
    queryFn: async () => (await purchasingReportsApi.summary({ date_from: dateFrom, date_to: dateTo })).data,
    enabled: !invalidRange,
  });
  const history = useQuery({
    queryKey: ["purchasing-price-history", dateFrom, dateTo, historySearch, historyPage],
    queryFn: () => purchasingReportsApi.priceHistory({ date_from: dateFrom, date_to: dateTo,
      search: historySearch.trim() || undefined, page: historyPage, page_size: 20 }),
    enabled: !invalidRange,
  });
  const data: any = query.data ?? {};
  const allowed = data.allowed !== false;

  if (!canAccess(user, PURCHASING_REPORT_ROLES, "reports.purchasing")) return <ForbiddenPage />;

  const requisitionCounts: Record<string, number> = data.requisitions?.status_counts ?? {};
  const poCounts: Record<string, number> = data.purchase_orders?.status_counts ?? {};
  const receiptCounts: Record<string, number> = data.receipts?.status_counts ?? {};
  const topSuppliers: any[] = data.top_suppliers ?? [];

  const statusRows = (counts: Record<string, number>) => Object.entries(counts).map(([status, count]) => ({ ...statusBadge(status), count: Number(count) })).sort((a: any, b: any) => b.count - a.count);

  return (
    <div className="space-y-6">
      <PurchasingExceptionPanel dateFrom={dateFrom} dateTo={dateTo}/>
      <PageHeader  actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="Purchasing Reports" description="Purchase requisition, purchase order and receiving activity summarized for the selected period." />
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">From</span>
            <input type="date" className={input} value={dateFrom} max={dateTo || undefined} onChange={(e) => { setDateFrom(e.target.value); setHistoryPage(1); }} />
          </label>
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">To</span>
            <input type="date" className={input} value={dateTo} min={dateFrom || undefined} onChange={(e) => { setDateTo(e.target.value); setHistoryPage(1); }} />
          </label>
          <Badge variant="secondary">Last updated: {query.isSuccess && !query.isFetching ? "ready" : "loading"}</Badge>
          {invalidRange && <span className="text-sm text-red-700">From date must be on or before To date.</span>}
        </div>
      </Card>

      {query.isLoading ? <Loading /> : !allowed || invalidRange ? null : (
        <>
          <div className="grid gap-3 md:grid-cols-3">
            <Card className="p-4">
              <div className="flex items-center justify-between"><span className="text-xs uppercase tracking-wide text-slate-500">Requisitions</span><Badge variant="warning">{num(data.requisitions?.total ?? 0)}</Badge></div>
              <div className="mt-2 text-2xl font-bold">{num(data.requisitions?.total ?? 0)}</div>
              <div className="mt-2 flex flex-wrap gap-1">{statusRows(requisitionCounts).map((row: any) => <Badge key={row.label} variant={row.variant}>{row.label}: {num(row.count)}</Badge>)}</div>
            </Card>
            <Card className="p-4">
              <div className="flex items-center justify-between"><span className="text-xs uppercase tracking-wide text-slate-500">Purchase Orders</span><Badge variant="info">{num(data.purchase_orders?.total ?? 0)}</Badge></div>
              <div className="mt-2 text-2xl font-bold">{num(data.purchase_orders?.total ?? 0)}</div>
              <div className="mt-2 flex flex-wrap gap-1">{statusRows(poCounts).map((row: any) => <Badge key={row.label} variant={row.variant}>{row.label}: {num(row.count)}</Badge>)}</div>
              <div className="mt-3 grid grid-cols-2 gap-3 border-t border-slate-100 pt-3 text-sm">
                <div><div className="text-xs text-slate-500">Committed value</div><div className="font-semibold">{money(data.purchase_orders?.committed_value)}</div></div>
                <div><div className="text-xs text-slate-500">Open POs</div><div className="font-semibold">{num(data.purchase_orders?.open_count ?? 0)} <span className="text-xs font-normal text-slate-400">({money(data.purchase_orders?.open_value)})</span></div></div>
              </div>
            </Card>
            <Card className="p-4">
              <div className="flex items-center justify-between"><span className="text-xs uppercase tracking-wide text-slate-500">Receipts</span><Badge variant="success">{num(data.receipts?.total ?? 0)}</Badge></div>
              <div className="mt-2 text-2xl font-bold">{num(data.receipts?.total ?? 0)}</div>
              <div className="mt-2 flex flex-wrap gap-1">{statusRows(receiptCounts).map((row: any) => <Badge key={row.label} variant={row.variant}>{row.label}: {num(row.count)}</Badge>)}</div>
              <div className="mt-3 grid grid-cols-2 gap-3 border-t border-slate-100 pt-3 text-sm">
                <div><div className="text-xs text-slate-500">Posted value</div><div className="font-semibold">{money(data.receipts?.posted_value)}</div></div>
                <div><div className="text-xs text-slate-500">Suppliers active</div><div className="font-semibold">{num(topSuppliers.length)}</div></div>
              </div>
            </Card>
          </div>

          <Card className="p-0">
            <div className="border-b px-4 py-3 text-sm font-semibold text-slate-700">Top Suppliers by Received Value</div>
            {topSuppliers.length === 0 ? (
              <div className="p-10 text-center text-sm text-slate-500">No receipts in the selected period.</div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full min-w-[640px] text-left text-sm">
                  <thead><tr className="border-b text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-4 py-3">#</th><th className="px-4 py-3">Supplier</th><th className="px-4 py-3 text-right">Receipts</th><th className="px-4 py-3 text-right">Received Value</th><th className="px-4 py-3 text-right">Share</th>
                  </tr></thead>
                  <tbody>
                    {topSuppliers.map((row, index) => (
                      <tr key={row.supplier_id} className="border-t">
                        <td className="px-4 py-3 text-slate-400">{index + 1}</td>
                        <td className="px-4 py-3 font-medium">{row.supplier_name}</td>
                        <td className="px-4 py-3 text-right">{num(row.receipt_count)}</td>
                        <td className="px-4 py-3 text-right font-semibold">{money(row.received_value)}</td>
                        <td className="px-4 py-3 text-right"><Badge variant="primary">{num(((Number(row.received_value) || 0) / (Number(data.receipts?.posted_value) || 1)) * 100)}%</Badge></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
          <Card className="p-0">
            <div className="flex flex-wrap items-end justify-between gap-3 border-b px-4 py-3">
              <div><h2 className="text-sm font-semibold text-slate-800">Purchase Price History</h2>
                <p className="mt-1 text-xs text-slate-500">Posted receiving lines, unit cost before tax. Search items, suppliers, or receipt numbers.</p></div>
              <label className="text-xs text-slate-600">Find item or supplier
                <input className={`${input} mt-1 block min-w-[230px]`} placeholder="Code, name, supplier, receipt"
                  value={historySearch} onChange={e => { setHistorySearch(e.target.value); setHistoryPage(1); }}/>
              </label>
            </div>
            {history.isError && <p className="p-4 text-sm text-red-700">Price history could not be loaded.</p>}
            {history.isLoading ? <Loading /> : <div className="overflow-x-auto"><table className="w-full min-w-[920px] text-sm">
              <thead><tr className="border-b text-left text-xs uppercase tracking-wide text-slate-500">
                <th className="px-4 py-3">Date / receipt</th><th className="px-4 py-3">Item</th>
                <th className="px-4 py-3">Supplier</th><th className="px-4 py-3 text-right">Qty</th>
                <th className="px-4 py-3 text-right">Unit cost</th><th className="px-4 py-3 text-right">Line cost</th>
              </tr></thead>
              <tbody>{(history.data?.items ?? []).map(row => <tr key={row.receipt_item_id} className="border-t">
                <td className="px-4 py-3"><div>{row.received_at.slice(0, 10)}</div>
                  <Link className="font-medium text-emerald-700 hover:underline" to={`/receiving/${row.receipt_id}`}>{row.receipt_number}</Link>
                  {row.purchase_order_number && <div className="text-xs text-slate-500">{row.purchase_order_number}</div>}</td>
                <td className="px-4 py-3"><div className="font-medium">{row.product_name}</div><div className="text-xs text-slate-500">{row.product_code}</div></td>
                <td className="px-4 py-3">{row.supplier_name}</td>
                <td className="px-4 py-3 text-right">{num(row.quantity)} {row.uom}</td>
                <td className="px-4 py-3 text-right font-medium">{money(row.unit_cost)}</td>
                <td className="px-4 py-3 text-right">{money(row.line_value)}</td>
              </tr>)}
                {!history.data?.items.length && !history.isLoading && <tr><td colSpan={6} className="p-8 text-center text-slate-500">No posted receiving lines in this period.</td></tr>}
              </tbody>
            </table></div>}
            <div className="flex items-center justify-end gap-3 border-t px-4 py-3 text-sm">
              <span className="text-slate-500">{num(history.data?.total_items ?? 0)} lines</span>
              <Button variant="outline" disabled={!history.data?.has_previous} onClick={() => setHistoryPage(page => Math.max(1, page - 1))}>Previous</Button>
              <span>{historyPage} / {Math.max(1, history.data?.total_pages ?? 0)}</span>
              <Button variant="outline" disabled={!history.data?.has_next} onClick={() => setHistoryPage(page => page + 1)}>Next</Button>
            </div>
          </Card>
        </>
      )}
    </div>
  );
}
