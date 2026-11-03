import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import api from "@/api/client";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import ReportUnitButtons from "@/components/reports/ReportUnitButtons";
import InventoryPrintButton from "@/components/print/InventoryPrintButton";
import { warehouseApi } from "@/modules/master/warehouses/api/warehouseApi";
import {
  collectReportPages,
  printMoney,
  printNumber,
} from "@/utils/inventoryPrint";
import { todayLocal } from "@/utils/dateConstraints";

type Row = {
  id: number;
  product_id: number;
  product_code: string;
  product_name: string;
  warehouse_id: number;
  warehouse: string;
  uom: string;
  missing_inventory_snapshot: boolean;
} & Record<string, number | string | boolean>;
type Page = {
  items: Row[];
  total_items: number;
  total_pages: number;
  summary: Record<string, number>;
  quantity_totals_by_uom: Array<{
    uom: string;
    opening: number;
    in_quantity: number;
    out_quantity: number;
    closing: number;
  }>;
};
const input =
  "h-9 min-w-0 rounded-md border border-slate-300 bg-white px-2 text-sm";
const columns = [
  ["opening_quantity", "Opening"],
  ["receiving_quantity", "Receiving"],
  ["operational_quantity", "Operational"],
  ["return_quantity", "Return"],
  ["replacement_quantity", "Replacement"],
  ["adjustment_quantity", "Adjustment"],
  ["other_quantity", "Other"],
  ["closing_quantity", "Closing"],
] as const;

export default function InventoryPeriodReportPage() {
  const [unit, setUnit] = useState("");
  const [from, setFrom] = useState(() => todayLocal().slice(0, 8) + "01");
  const [to, setTo] = useState(todayLocal);
  const [warehouse, setWarehouse] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [measure, setMeasure] = useState("quantity");
  const keyFor = (key: string) =>
    measure === "value" ? key.replace("_quantity", "_value") : key;
  const format = (value: unknown) =>
    measure === "value" ? printMoney(value) : printNumber(value);
  const [exporting, setExporting] = useState(false);
  const warehouses = useQuery({
    queryKey: ["inventory-period-warehouses"],
    queryFn: async () => (await warehouseApi.list()).data,
  });
  const params = {
    date_from: from,
    date_to: to,
    business_unit_id: Number(unit) || undefined,
    warehouse_id: Number(warehouse) || undefined,
    search: search.trim() || undefined,
  };
  const valid = !!from && !!to && from <= to;
  const query = useQuery({
    queryKey: ["inventory-period-report", params, page],
    queryFn: async () =>
      (
        await api.get<Page>("/inventory/period-report", {
          params: { ...params, page, page_size: 50 },
        })
      ).data,
    enabled: valid,
  });
  const all = () =>
    collectReportPages<Row>(
      async (p) =>
        (
          await api.get<Page>("/inventory/period-report", {
            params: { ...params, page: p, page_size: 100 },
          })
        ).data,
    );
  const context = `${from} to ${to} · Unit ${unit || "All"} · Warehouse ${warehouse || "All"} · ${search || "All items"}`;
  const exportExcel = async () => {
    setExporting(true);
    try {
      const data = await all();
      const XLSX = await import("xlsx");
      const workbook = XLSX.utils.book_new();
      const first = XLSX.utils.aoa_to_sheet([
        ["Stock movement summary"],
        [context],
        ["Value basis", "Warehouse carrying cost"],
        [],
        ["Metric", "Value"],
        ...Object.entries((data as Page).summary),
      ]);
      first["!cols"] = [{ wch: 28 }, { wch: 70 }];
      XLSX.utils.book_append_sheet(workbook, first, "Summary");
      const detail = XLSX.utils.json_to_sheet(
        data.items.map((r) => ({
          Code: r.product_code,
          Description: r.product_name,
          Warehouse: r.warehouse,
          UOM: r.uom,
          ...Object.fromEntries(
            columns.flatMap(([key, title]) => [
              [`${title} quantity`, Number(r[key])],
              [`${title} value`, Number(r[key.replace("_quantity", "_value")])],
            ]),
          ),
          "Opening value": Number(r.opening_value),
          "Incoming value": Number(r.in_value),
          "Outgoing value": Number(r.out_value),
          "Closing value": Number(r.closing_value),
          "Snapshot missing": r.missing_inventory_snapshot ? "Review" : "",
        })),
      );
      detail["!cols"] = [
        { wch: 16 },
        { wch: 38 },
        { wch: 20 },
        { wch: 8 },
        ...Array.from({ length: 21 }, () => ({ wch: 18 })),
      ];
      if (detail["!ref"]) detail["!autofilter"] = { ref: detail["!ref"] };
      XLSX.utils.book_append_sheet(workbook, detail, "Stock Detail");
      XLSX.writeFile(workbook, `Stock-${from}-${to}.xlsx`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Export failed");
    } finally {
      setExporting(false);
    }
  };
  return (
    <div className="space-y-3">
      <PageHeader
        title="Stock Movement Summary"
        actions={
          <>
            <Button
              variant="outline"
              disabled={!valid || exporting}
              onClick={exportExcel}
            >
              {exporting ? "Preparing…" : "Excel"}
            </Button>
            <InventoryPrintButton
              disabled={!valid}
              loadReport={async () => {
                const data = await all();
                return {
                  title: "Stock Movement Summary",
                  context: context + ` · ${measure}`,
                  columns: [
                    { label: "Code", code: true },
                    { label: "Description" },
                    { label: "Warehouse" },
                    { label: "UOM" },
                    ...columns.map(([, title]) => ({
                      label: title,
                      numeric: true,
                    })),
                    { label: "Closing value", numeric: true },
                  ],
                  groups: [
                    {
                      title: "Stock detail",
                      rows: data.items.map((r) => [
                        r.product_code,
                        r.product_name,
                        r.warehouse,
                        r.uom,
                        ...columns.map(([key]) => format(r[keyFor(key)])),
                        printMoney(r.closing_value),
                      ]),
                    },
                  ],
                  rowCount: data.items.length,
                };
              }}
            />
          </>
        }
      />
      <ReportUnitButtons
        value={unit}
        onChange={(value) => {
          setUnit(value);
          setWarehouse("");
          setPage(1);
        }}
      />
      <Card className="flex flex-wrap items-end gap-3 p-3">
        <label className="flex flex-col gap-1 text-xs">
          From
          <input
            className={input}
            type="date"
            value={from}
            onChange={(e) => {
              setFrom(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          To
          <input
            className={input}
            type="date"
            value={to}
            onChange={(e) => {
              setTo(e.target.value);
              setPage(1);
            }}
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          Warehouse
          <select
            className={input}
            value={warehouse}
            onChange={(e) => {
              setWarehouse(e.target.value);
              setPage(1);
            }}
          >
            <option value="">All accessible warehouses</option>
            {warehouses.data?.map(
              (w: { id: number; code: string; name: string }) => (
                <option key={w.id} value={w.id}>
                  {w.code} — {w.name}
                </option>
              ),
            )}
          </select>
        </label>
        <label className="flex min-w-40 flex-1 flex-col gap-1 text-xs">
          Item
          <input
            className={input}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(1);
            }}
            placeholder="Code or description"
          />
        </label>
        <label className="flex flex-col gap-1 text-xs">
          Measure
          <select
            className={input}
            value={measure}
            onChange={(e) => setMeasure(e.target.value)}
          >
            <option value="quantity">Quantity</option>
            <option value="value">Value (IDR)</option>
          </select>
        </label>
        <Button
          variant="outline"
          onClick={() => query.refetch()}
          disabled={!valid || query.isFetching}
        >
          Refresh
        </Button>
      </Card>
      {!valid && (
        <p role="alert" className="text-sm text-red-700">
          Choose a valid date range.
        </p>
      )}
      {query.isError && (
        <p role="alert" className="text-sm text-red-700">
          Unable to load the stock report.
        </p>
      )}
      <Card className="flex flex-wrap gap-6 p-3 text-sm">
        {[
          ["opening_value", "Opening value"],
          ["in_value", "Incoming"],
          ["out_value", "Outgoing"],
          ["closing_value", "Closing value"],
        ].map(([key, title]) => (
          <div key={key}>
            <span className="text-xs text-slate-500">{title}</span>
            <div className="font-semibold tabular-nums">
              {printMoney(query.data?.summary[key])}
            </div>
          </div>
        ))}
      </Card>
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full whitespace-nowrap text-xs">
            <thead className="bg-slate-50">
              <tr>
                <th className="p-2 text-left">Code / Description</th>
                <th>Warehouse</th>
                <th>UOM</th>
                {columns.map(([key, title]) => (
                  <th className="p-2 text-right" key={key}>
                    {title}
                  </th>
                ))}
                <th className="p-2 text-right">Closing value</th>
              </tr>
            </thead>
            <tbody>
              {query.data?.items.map((row) => (
                <tr key={row.id} className="border-t">
                  <td className="p-2">
                    <Link
                      className="font-medium text-emerald-700 underline"
                      to={`/inventory/movements?product_id=${row.product_id}&warehouse_id=${row.warehouse_id}&date_from=${from}&date_to=${to}`}
                    >
                      {row.product_code}
                    </Link>
                    <div className="max-w-72 truncate">{row.product_name}</div>
                    {row.missing_inventory_snapshot && (
                      <span className="text-amber-700">
                        Inventory snapshot missing — review
                      </span>
                    )}
                  </td>
                  <td>{row.warehouse}</td>
                  <td>{row.uom}</td>
                  {columns.map(([key]) => (
                    <td key={key} className="p-2 text-right tabular-nums">
                      {format(row[keyFor(key)])}
                    </td>
                  ))}
                  <td className="p-2 text-right tabular-nums">
                    {printMoney(row.closing_value)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="flex items-center justify-end gap-3 p-3 text-xs">
          <span>{query.data?.total_items ?? 0} stock lines</span>
          <Button
            variant="outline"
            disabled={page === 1 || query.isFetching}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </Button>
          <span>
            {page} / {Math.max(1, query.data?.total_pages ?? 1)}
          </span>
          <Button
            variant="outline"
            disabled={
              page >= (query.data?.total_pages ?? 1) || query.isFetching
            }
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </Button>
        </div>
      </Card>
      <div className="flex flex-wrap gap-4 text-xs">
        {query.data?.quantity_totals_by_uom.map((row) => (
          <span key={row.uom}>
            {row.uom}: {printNumber(row.opening)} +{" "}
            {printNumber(row.in_quantity)} − {printNumber(row.out_quantity)} ={" "}
            <strong>{printNumber(row.closing)}</strong>
          </span>
        ))}
      </div>
    </div>
  );
}
