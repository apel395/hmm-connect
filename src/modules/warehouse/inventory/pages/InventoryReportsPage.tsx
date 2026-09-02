import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import Badge from "@/components/ui/Badge";
import { inventoryApi } from "../api";
import { warehouseApi } from "@/modules/master/warehouses/api/warehouseApi";

const money = (v: unknown) => "Rp " + Number(v ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (v: unknown) => Number(v ?? 0).toLocaleString("id-ID");

type Section = "valuation" | "low-stock" | "by-warehouse";

const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

export default function InventoryReportsPage() {
  const [section, setSection] = useState<Section>("valuation");

  const warehousesQuery = useQuery({
    queryKey: ["inventory-report-warehouses"],
    queryFn: async () => (await warehouseApi.list()).data,
  });
  const warehouses: any[] = warehousesQuery.data ?? [];

  const overall = useQuery({
    queryKey: ["inventory-report-overall"],
    queryFn: async () => (await inventoryApi.list({ page: 1, page_size: 100 })).data,
  });
  const overallData: any = overall.data ?? {};
  const overallSummary = overallData.summary ?? {};

  const lowStock = useQuery({
    queryKey: ["inventory-report-low-stock"],
    queryFn: async () => (await inventoryApi.list({ page: 1, page_size: 100, health: "LOW_STOCK" })).data,
  });
  const lowStockData: any = lowStock.data ?? {};
  const lowStockItems: any[] = lowStockData.items ?? [];

  const byWarehouse = useQuery({
    queryKey: ["inventory-report-by-warehouse", warehouses.length],
    queryFn: async () => {
      const rows = await Promise.all(
        warehouses.map(async (w) => {
          const data = await (await inventoryApi.list({ page: 1, page_size: 1, warehouse_id: w.id })).data;
          const s = data.summary ?? {};
          return {
            id: w.id,
            code: w.code,
            name: w.name,
            stock_value: s.stock_value ?? 0,
            stock_lines: s.stock_lines ?? 0,
            low_stock: s.low_stock ?? 0,
          };
        })
      );
      return rows;
    },
    enabled: warehouses.length > 0,
  });

  const show = section === "valuation" ? overall.isLoading : section === "by-warehouse" ? warehousesQuery.isLoading || byWarehouse.isLoading : lowStock.isLoading;

  return (
    <div className="space-y-6">
      <PageHeader title="Inventory Reports" description="Stock valuation and movement insights computed from current warehouse inventory." />
      <Card className="p-4">
        <div className="flex flex-wrap items-end gap-3">
          <label className="block">
            <span className="mb-1 block text-xs font-medium text-slate-500">Report</span>
            <select className={input} value={section} onChange={(e) => setSection(e.target.value as Section)}>
              <option value="valuation">Valuation Summary</option>
              <option value="by-warehouse">Valuation by Warehouse</option>
              <option value="low-stock">Low Stock / Reorder</option>
            </select>
          </label>
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Badge variant="success">{num(overallSummary.stock_lines ?? 0)} stock lines</Badge>
            <Badge variant="secondary">{money(overallSummary.stock_value)}</Badge>
            <Badge variant="danger">{num(overallSummary.low_stock ?? 0)} low stock</Badge>
          </div>
        </div>
      </Card>

      {show
        ? <Loading />
        : section === "valuation" ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Total Stock Value</div><div className="mt-2 text-2xl font-bold">{money(overallSummary.stock_value)}</div></Card>
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Stock Lines</div><div className="mt-2 text-2xl font-bold">{num(overallSummary.stock_lines ?? 0)}</div></Card>
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Monitored Lines</div><div className="mt-2 text-2xl font-bold">{num(overallSummary.monitored_lines ?? 0)}</div></Card>
            <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Low Stock</div><div className="mt-2 text-2xl font-bold text-red-700">{num(overallSummary.low_stock ?? 0)}</div></Card>
          </div>
        ) : section === "by-warehouse" ? (
          <Card className="p-0">
            <table className="w-full text-left text-sm">
              <thead><tr className="border-b text-slate-500"><th className="px-4 py-3">Warehouse</th><th className="px-4 py-3 text-right">Stock Lines</th><th className="px-4 py-3 text-right">Low Stock</th><th className="px-4 py-3 text-right">Stock Value</th></tr></thead>
              <tbody>
                {(byWarehouse.data ?? []).map((row) => (
                  <tr key={row.id} className="border-t">
                    <td className="px-4 py-3"><span className="font-semibold">{row.name}</span> <span className="text-slate-400">({row.code})</span></td>
                    <td className="px-4 py-3 text-right">{num(row.stock_lines)}</td>
                    <td className="px-4 py-3 text-right"><span className={Number(row.low_stock) > 0 ? "text-red-700" : ""}>{num(row.low_stock)}</span></td>
                    <td className="px-4 py-3 text-right font-semibold">{money(row.stock_value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </Card>
        ) : (
          <Card className="p-0">
            {lowStockItems.length === 0 ? (
              <div className="p-10 text-center text-sm text-slate-500">No warehouse stock is at or below its minimum threshold.</div>
            ) : (
              <table className="w-full text-left text-sm">
                <thead><tr className="border-b text-slate-500"><th className="px-4 py-3">Product</th><th className="px-4 py-3">Warehouse</th><th className="px-4 py-3 text-right">On Hand</th><th className="px-4 py-3 text-right">Minimum</th><th className="px-4 py-3 text-right">Shortage</th></tr></thead>
                <tbody>
                  {lowStockItems.map((row) => (
                    <tr key={row.id} className="border-t">
                      <td className="px-4 py-3"><span className="font-semibold">{row.product_name}</span> <span className="text-slate-400">({row.product_code})</span></td>
                      <td className="px-4 py-3">{row.warehouse_name}</td>
                      <td className="px-4 py-3 text-right">{num(row.quantity)} {row.uom}</td>
                      <td className="px-4 py-3 text-right">{num(row.minimum_stock)}</td>
                      <td className="px-4 py-3 text-right font-semibold text-red-700">{num(row.shortage)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        )}
    </div>
  );
}
