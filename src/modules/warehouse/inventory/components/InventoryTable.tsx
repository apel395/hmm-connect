import { ArrowUpRight, Copy, PackageOpen } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import type { Inventory } from "../types";

import { STOCK_COLUMNS, type StockColumn } from "./stockTableSettings";
const money = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
const quantity = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });

export default function InventoryTable({
  rows,
  columns,
  onSelect,
  selectedId,
  compact = false,
}: {
  rows: Inventory[];
  columns?: StockColumn[];
  onSelect?: (row: Inventory) => void;
  selectedId?: number;
  compact?: boolean;
}) {
  const visible = (id: StockColumn) => !columns || columns.includes(id);
  const copyCode = async (code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      toast.success("Item code copied");
    } catch {
      toast.error("Unable to copy item code");
    }
  };
  return (
    <div
      className={`stock-table-scroll ${compact ? "stock-table-dense" : ""}`}
      tabIndex={0}
      role="region"
      aria-label="Warehouse stock table"
    >
      <table
        className="stock-data-table"
        aria-label="Stock by item and warehouse"
        style={{
          minWidth:
            452 +
            STOCK_COLUMNS.filter((c) => visible(c.id)).reduce(
              (sum, c) => sum + c.width,
              0,
            ),
        }}
      >
        <colgroup>
          <col style={{ width: 142 }} />
          <col />
          {STOCK_COLUMNS.filter((c) => visible(c.id)).map((c) => (
            <col key={c.id} style={{ width: c.width }} />
          ))}
          <col style={{ width: 40 }} />
        </colgroup>
        <thead>
          <tr>
            <th className="stock-code-col">Item code</th>
            <th className="stock-name-col">Item name</th>
            {visible("warehouse") && <th>Warehouse</th>}
            {visible("quantity") && <th className="stock-number">On hand</th>}
            {visible("uom") && <th>Unit</th>}
            {visible("cost") && <th className="stock-number">Avg. cost</th>}
            {visible("value") && <th className="stock-number">Stock value</th>}
            {visible("status") && <th>Status</th>}
            <th className="stock-row-action">
              <span className="sr-only">Stock card</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id} data-selected={row.id === selectedId || undefined}>
              <td className="stock-code-col">
                <div className="group/code flex items-center justify-between gap-1">
                  <span
                    title={row.product_code}
                    className="inventory-item-code truncate font-mono text-[11px] font-semibold text-emerald-800"
                  >
                    {row.product_code}
                  </span>
                  <button
                    type="button"
                    className="stock-copy opacity-0 group-hover/code:opacity-100 focus:opacity-100"
                    title={`Copy ${row.product_code}`}
                    aria-label={`Copy ${row.product_code}`}
                    onClick={() => void copyCode(row.product_code)}
                  >
                    <Copy size={12} />
                  </button>
                </div>
              </td>
              <td className="stock-name-col">
                {onSelect ? (
                  <button
                    type="button"
                    className="stock-item-name"
                    title={row.product_name}
                    aria-label={`View ${row.product_name}`}
                    onClick={() => onSelect(row)}
                  >
                    {row.product_name}
                  </button>
                ) : (
                  <span className="stock-item-name" title={row.product_name}>
                    {row.product_name}
                  </span>
                )}
              </td>
              {visible("warehouse") && (
                <td>
                  <span title={row.warehouse_name}>{row.warehouse_name}</span>
                  <span className="ml-2 text-[11px] text-slate-400">
                    {row.warehouse_code}
                  </span>
                </td>
              )}
              {visible("quantity") && (
                <td
                  className={`stock-number font-semibold ${Number(row.quantity) < 0 ? "text-red-600" : ""}`}
                >
                  {quantity(row.quantity)}
                </td>
              )}
              {visible("uom") && <td className="text-slate-500">{row.uom}</td>}
              {visible("cost") && (
                <td className="stock-number text-slate-500">
                  {money(row.average_cost)}
                </td>
              )}
              {visible("value") && (
                <td className="stock-number font-semibold text-slate-900">
                  {money(row.stock_value)}
                </td>
              )}
              {visible("status") && (
                <td>
                  <span
                    className={`stock-status ${Number(row.quantity) <= 0 ? "stock-status-empty" : row.low_stock || row.needs_reorder ? "stock-status-low" : "stock-status-good"}`}
                  >
                    <i />
                    {Number(row.quantity) <= 0
                      ? "No stock"
                      : row.low_stock || row.needs_reorder
                        ? "Reorder"
                        : "In stock"}
                  </span>
                </td>
              )}
              <td className="stock-row-action">
                <Link
                  title={`Open stock card for ${row.product_code}`}
                  aria-label={`Open stock card for ${row.product_code}`}
                  to={`/inventory/movements?product_id=${row.product_id}&warehouse_id=${row.warehouse_id}`}
                  className="stock-action-link"
                >
                  <ArrowUpRight size={15} />
                </Link>
              </td>
            </tr>
          ))}
          {!rows.length && (
            <tr>
              <td colSpan={3 + (columns?.length ?? 6)}>
                <div className="flex min-h-52 flex-col items-center justify-center gap-2 text-slate-400">
                  <PackageOpen size={32} strokeWidth={1.3} />
                  <strong className="text-sm font-medium text-slate-700">
                    No stock matches this view
                  </strong>
                  <span className="text-xs">
                    Try another item, warehouse or date.
                  </span>
                </div>
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
