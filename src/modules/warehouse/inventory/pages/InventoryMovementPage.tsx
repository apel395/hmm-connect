import InventoryPrintButton from "@/components/print/InventoryPrintButton";
import { movementReport } from "@/modules/warehouse/inventory/print/reports";
import InventoryReportHeading from "@/components/print/InventoryReportHeading";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import { SlidersHorizontal, X } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { TABLE_UI } from "@/config/tableUi";
import { listLocations } from "@/modules/admin/organization/api";
import { inventoryApi } from "../api";
import type { InventoryMovement, InventoryMovementFilters } from "../movement";
import { useInventoryMovements } from "../useInventoryMovement";

const input = "mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const quantity = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });
const money = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});
type SourceFilter = NonNullable<InventoryMovementFilters["source_kind"]> | "ALL";
const eventDirection = (row: InventoryMovement): "IN" | "OUT" | null => {
  if (row.movement_type === "IN" || row.movement_type === "OUT") return row.movement_type;
  if (Number(row.in_quantity) > 0 && Number(row.out_quantity) === 0) return "IN";
  if (Number(row.out_quantity) > 0 && Number(row.in_quantity) === 0) return "OUT";
  return null;
};

function eventName(row: InventoryMovement) {
  const direction = eventDirection(row);
  return <span className="inline-flex items-center gap-2">
    {direction && <span className={direction === "IN"
      ? "rounded bg-emerald-100 px-1.5 py-0.5 text-xs font-bold text-emerald-800"
      : "rounded bg-rose-100 px-1.5 py-0.5 text-xs font-bold text-rose-800"}>
      {direction}
    </span>}
  </span>;
}


function sourceDocuments(row: InventoryMovement) {
  return <div className="inline-flex items-center gap-2 whitespace-nowrap">
    {row.goods_receipt_id && <Link className={TABLE_UI.documentLink} to={`/receiving/${row.goods_receipt_id}`}>
      {row.receipt_number ?? row.reference_number ?? `Receiving #${row.goods_receipt_id}`}
    </Link>}
    {row.purchase_order_id && <Link className={TABLE_UI.documentLink} to={`/purchase-orders/${row.purchase_order_id}`}>
      {row.purchase_order_number ?? `PO #${row.purchase_order_id}`}
    </Link>}
    {row.reference_type === "STORE_REQUEST" && row.reference_id &&
      <Link className={TABLE_UI.documentLink} to={`/store-requests/${row.reference_id}`}>{row.reference_number ?? `Store Request #${row.reference_id}`}</Link>}
    {row.reference_type === "STOCK_OPNAME" && row.reference_id &&
      <Link className={TABLE_UI.documentLink} to={`/stock-opnames/${row.reference_id}`}>{row.reference_number ?? `Stock Opname #${row.reference_id}`}</Link>}
    {row.reference_type === "STOCK_ADJUSTMENT" && row.reference_id &&
      <Link className={TABLE_UI.documentLink} to="/stock-adjustments">{row.reference_number ?? `Stock Adjustment #${row.reference_id}`}</Link>}
    {!row.goods_receipt_id && !row.purchase_order_id &&
      !["STORE_REQUEST", "STOCK_OPNAME", "STOCK_ADJUSTMENT"].includes(row.reference_type ?? "") &&
      <span className="text-slate-500">{row.reference_number && row.reference_number !== "-" ? row.reference_number : "—"}</span>}
  </div>;
}

export default function InventoryMovementPage() {
  const [params, setParams] = useSearchParams();
  const [productId, setProductId] = useState(params.get("product_id") ?? "");
  const [warehouseId, setWarehouseId] = useState(params.get("warehouse_id") ?? "");
  const [poId, setPoId] = useState(params.get("purchase_order_id") ?? "");
  const [receiptId, setReceiptId] = useState(params.get("goods_receipt_id") ?? "");
  const [locationId, setLocationId] = useState(params.get("location_id") ?? "");
  const [departmentId, setDepartmentId] = useState(params.get("department_id") ?? "");
  const [accountId, setAccountId] = useState(params.get("account_id") ?? "");
  const [sourceKind, setSourceKind] = useState<SourceFilter>("ALL");
  const [dateFrom, setDateFrom] = useState(params.get("date_from") ?? "");
  const [dateTo, setDateTo] = useState(params.get("date_to") ?? "");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => Number(window.localStorage.getItem("stock-movement-page-size")) === 100 ? 100 : 50);
  const [showFilters, setShowFilters] = useState(false);

  const accounts = useQuery({ queryKey: ["inventory-coa-filter"], queryFn: inventoryApi.accounts });
  const locations = useQuery({ queryKey: ["stock-movement-locations"], queryFn: () => listLocations({ is_active: true, assigned_only: true }) });
  const filters = useMemo<InventoryMovementFilters>(() => ({
    product_id: productId ? Number(productId) : undefined,
    warehouse_id: warehouseId ? Number(warehouseId) : undefined,
    purchase_order_id: poId ? Number(poId) : undefined,
    goods_receipt_id: receiptId ? Number(receiptId) : undefined,
    location_id: locationId ? Number(locationId) : undefined,
    department_id: departmentId ? Number(departmentId) : undefined,
    account_id: accountId ? Number(accountId) : undefined,
    source_kind: sourceKind === "ALL" ? undefined : sourceKind,
    date_from: dateFrom || undefined, date_to: dateTo || undefined,
    search: search.trim() || undefined, page, page_size: pageSize,
  }), [productId, warehouseId, poId, receiptId, locationId, departmentId, accountId,
    sourceKind, dateFrom, dateTo, search, page, pageSize]);
  const query = useInventoryMovements(filters);
  const result = query.data;
  const rows = result?.items ?? [];
  const history = result?.history_balances ?? [];
  const pages = Math.max(result?.total_pages ?? 0, 1);
  const total = result?.total_items ?? 0;
  const summary = result?.summary;
  const byAccount = result?.totals_by_account ?? [];
  const focused = Boolean(productId);
  const invalidRange = Boolean(dateFrom && dateTo && dateFrom > dateTo);
  const openingQuantity = history.reduce((sum, item) => sum + Number(item.opening_quantity), 0);
  const closingQuantity = history.reduce((sum, item) => sum + Number(item.closing_quantity), 0);

  useEffect(() => setPage(1), [productId, warehouseId, poId, receiptId, locationId,
    departmentId, accountId, sourceKind, dateFrom, dateTo, search, pageSize]);
  useEffect(() => window.localStorage.setItem("stock-movement-page-size", String(pageSize)), [pageSize]);
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);

  const numeric = (setter: (value: string) => void) =>
    (event: React.ChangeEvent<HTMLInputElement>) => setter(event.target.value.replace(/\D/g, ""));
  const focusItem = (row: InventoryMovement) => {
    setProductId(String(row.product_id));
    setWarehouseId(String(row.warehouse_id));
    setSearch("");
    const next = new URLSearchParams(params);
    next.set("product_id", String(row.product_id));
    next.set("warehouse_id", String(row.warehouse_id));
    setParams(next, { replace: true });
  };
  const clearItem = () => {
    setProductId("");
    setWarehouseId("");
    const next = new URLSearchParams(params);
    next.delete("product_id");
    next.delete("warehouse_id");
    setParams(next, { replace: true });
  };

  return <div className="inventory-print-report space-y-3">
    <InventoryReportHeading title={focused ? "Item Stock History" : "Stock Movement"} context={`Period: ${dateFrom || "2026-01-01"} – ${dateTo || "Current"}${search ? ` · Search: ${search}` : ""}${productId ? ` · Item ID: ${productId}` : ""}${warehouseId ? ` · Warehouse ID: ${warehouseId}` : ""}${accountId ? ` · Account ID: ${accountId}` : ""}${locationId ? ` · Location ID: ${locationId}` : ""}${departmentId ? ` · Department ID: ${departmentId}` : ""}${poId ? ` · PO ID: ${poId}` : ""}${receiptId ? ` · Receipt ID: ${receiptId}` : ""} · Source: ${sourceKind}`} rows={rows.length} total={total}/>
    <PageHeader title={focused ? "Item Stock History" : "Stock Movement"}
      description={focused
        ? "Opening stock, purchases, usage, and adjustments in date order. The running quantity follows the item in each warehouse."
        : "Search or select an item to see its complete stock history and running quantity."}
      actions={<div className="flex gap-2">
        {focused && <Button variant="secondary" onClick={clearItem}><X size={16} className="mr-1"/> All items</Button>}
        <InventoryPrintButton disabled={invalidRange} loadReport={() => movementReport({...filters}, `Period: ${dateFrom || "All"} – ${dateTo || "Current"} · Search: ${search || "All"} · Source: ${sourceKind}${productId ? ` · Item ID: ${productId}` : ""}${warehouseId ? ` · Warehouse ID: ${warehouseId}` : ""}${locationId ? ` · Location: ${locations.data?.find(l => l.id === Number(locationId))?.name || locationId}` : ""}${departmentId ? ` · Department ID: ${departmentId}` : ""}${accountId ? ` · Account: ${accounts.data?.find(a => a.id === Number(accountId))?.account_name || accountId}` : ""}${poId ? ` · PO ID: ${poId}` : ""}${receiptId ? ` · Receipt ID: ${receiptId}` : ""}`)}/>
      </div>}/>

    <Card className="p-3 print:hidden">
      <div className="flex flex-wrap items-end gap-2">
        <label className="min-w-[220px] flex-1 text-xs font-medium text-slate-600">Search item or warehouse
          <input className={input} placeholder="Item code, name or warehouse" value={search} onChange={e => setSearch(e.target.value)}/>
        </label>
        <label className="min-w-[180px] text-xs font-medium text-slate-600">History event
          <select className={input} value={sourceKind} onChange={e => setSourceKind(e.target.value as SourceFilter)}>
            <option value="ALL">All events</option><option value="PURCHASE">Pembelian / Receiving</option>
            <option value="USAGE">Pemakaian</option><option value="ADJUSTMENT">Penyesuaian / Stock Opname</option>
          </select>
        </label>
        <Button type="button" size="sm" variant="outline" aria-expanded={showFilters} onClick={() => setShowFilters(value => !value)}>
          <SlidersHorizontal size={15}/> Filters{[productId,warehouseId,poId,receiptId,locationId,departmentId,accountId,dateFrom,dateTo].filter(Boolean).length ? ` (${[productId,warehouseId,poId,receiptId,locationId,departmentId,accountId,dateFrom,dateTo].filter(Boolean).length})` : ""}
        </Button>
      </div>
      {showFilters && <div className="mt-3 grid gap-2 border-t border-slate-100 pt-3 md:grid-cols-2 xl:grid-cols-4">
        <label className="text-xs font-medium text-slate-600">Item ID
          <input className={input} inputMode="numeric" value={productId} onChange={numeric(setProductId)} placeholder="All items"/>
        </label>
        <label className="text-xs font-medium text-slate-600">Warehouse ID
          <input className={input} inputMode="numeric" value={warehouseId} onChange={numeric(setWarehouseId)} placeholder="All warehouses"/>
        </label>
        <label className="text-xs font-medium text-slate-600">From date
          <input type="date" className={input} value={dateFrom} max={dateTo || undefined} onChange={e => setDateFrom(e.target.value)}/>
        </label>
        <label className="text-xs font-medium text-slate-600">To date
          <input type="date" className={input} value={dateTo} min={dateFrom || undefined} onChange={e => setDateTo(e.target.value)}/>
        </label>
        <label className="text-xs font-medium text-slate-600">Inventory account
          <select className={input} value={accountId} onChange={e => setAccountId(e.target.value)}>
            <option value="">All inventory COA</option>
            {(accounts.data ?? []).map(account => <option key={account.id} value={account.id}>
              {account.account_number} — {account.account_name}
            </option>)}
          </select>
        </label>
        <label className="text-xs font-medium text-slate-600">PO ID
          <input className={input} inputMode="numeric" value={poId} onChange={numeric(setPoId)} placeholder="All PO"/>
        </label>
        <label className="text-xs font-medium text-slate-600">Receiving ID
          <input className={input} inputMode="numeric" value={receiptId} onChange={numeric(setReceiptId)} placeholder="All receiving"/>
        </label>
        <label className="text-xs font-medium text-slate-600">Location
          <select className={input} value={locationId} onChange={e => setLocationId(e.target.value)}>
            <option value="">All locations</option>
            {(locations.data ?? []).map(location => <option key={location.id} value={location.id}>
              {location.name} ({location.code})
            </option>)}
            {locationId && !locations.isLoading && !locations.data?.some(location => String(location.id) === locationId) &&
              <option value={locationId}>Location #{locationId} (unavailable)</option>}
          </select>
          {locations.isError && <span className="mt-1 block text-xs text-red-700">Locations could not be loaded.</span>}
        </label>
        <label className="text-xs font-medium text-slate-600">Department ID
          <input className={input} inputMode="numeric" value={departmentId} onChange={numeric(setDepartmentId)} placeholder="All departments"/>
        </label>
      </div>}
      {invalidRange && <p className="mt-3 text-sm text-red-700">From date must be on or before To date.</p>}
      {focused && <p className="mt-3 text-xs text-slate-500">Stock balances include every event for this item and warehouse, even when event or document filters narrow the visible rows.</p>}
    </Card>

    {query.isError && <Card className="p-4 text-sm text-red-700">Stock history could not be loaded. Check the filters and try again.</Card>}
    {query.isLoading ? <Loading/> : <>
      {focused && <>
        <div className="grid gap-3 md:grid-cols-3">
          <Card className="p-3"><div className="text-xs uppercase text-slate-500">Stock awal · {result?.history_period?.date_from ?? "2026-01-01"}</div>
            <div className="mt-1 text-2xl font-bold">{quantity(openingQuantity)}</div></Card>
          <Card className="p-3"><div className="text-xs uppercase text-slate-500">Stock akhir · {result?.history_period?.date_to ?? "today"}</div>
            <div className="mt-1 text-2xl font-bold">{quantity(closingQuantity)}</div></Card>
          <Card className="p-3"><div className="text-xs uppercase text-slate-500">Matching events</div>
            <div className="mt-1 text-2xl font-bold">{total}</div></Card>
        </div>
        <Card className="overflow-x-auto p-0">
          <div className="border-b px-3 py-2 font-semibold">Opening and closing by warehouse</div>
          <table className="w-full min-w-[580px] text-sm"><thead><tr>
            <th className="px-4 py-2 text-left">Warehouse</th><th className="px-4 py-2 text-right">Opening qty</th>
            <th className="px-4 py-2 text-right">Closing qty</th>
          </tr></thead><tbody>{history.map(item => <tr key={item.warehouse_id} className="border-t">
            <td className="px-4 py-2">{item.warehouse_code} — {item.warehouse_name}</td>
            <td className="px-4 py-2 text-right">{quantity(item.opening_quantity)}</td>
            <td className="px-4 py-2 text-right font-semibold">{quantity(item.closing_quantity)}</td>
          </tr>)}</tbody></table>
          <p className="border-t px-4 py-2 text-xs text-slate-500">Opening quantity is reconstructed from current stock and recorded movements. It is a balance, not an additional stock transaction.</p>
        </Card>
      </>}

      <div className="grid gap-3 md:grid-cols-3">
        {!focused && <Card className="p-3"><div className="text-xs uppercase text-slate-500">Matching events</div><div className="mt-1 text-2xl font-bold">{total}</div></Card>}
        <Card className="p-3"><div className="text-xs uppercase text-slate-500">Filtered stock in</div><div className="mt-1 text-xl font-bold">Rp {money(summary?.in_value)}</div></Card>
        <Card className="p-3"><div className="text-xs uppercase text-slate-500">Filtered stock out</div><div className="mt-1 text-xl font-bold">{quantity(summary?.out_qty)} · Rp {money(summary?.out_value)}</div></Card>
      </div>

      <Card className="overflow-x-auto p-0">
        <div className="border-b px-3 py-2 font-semibold">Filtered totals by inventory account</div>
        <table className="w-full min-w-[790px] text-sm"><thead><tr>
          <th className="px-4 py-2 text-left">Inventory COA</th><th className="px-4 py-2 text-right">IN Qty</th>
          <th className="px-4 py-2 text-right">OUT Qty</th><th className="px-4 py-2 text-right">Net Qty</th>
          <th className="px-4 py-2 text-right">IN Value</th><th className="px-4 py-2 text-right">OUT Value</th>
        </tr></thead><tbody>{byAccount.map(row => <tr key={row.account_id ?? "none"} className="border-t">
          <td className="px-4 py-2">{row.account_code ? `${row.account_code} — ${row.account_name}` : "Unmapped"}</td>
          <td className="px-4 py-2 text-right">{quantity(row.in_qty)}</td><td className="px-4 py-2 text-right">{quantity(row.out_qty)}</td>
          <td className="px-4 py-2 text-right">{quantity(row.net_qty)}</td><td className="px-4 py-2 text-right">Rp {money(row.in_value)}</td>
          <td className="px-4 py-2 text-right">Rp {money(row.out_value)}</td>
        </tr>)}{!byAccount.length && <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500">No events for the selected filters.</td></tr>}</tbody></table>
      </Card>

      <Card className="overflow-hidden p-0">
        <div className="border-b px-3 py-2 font-semibold">{focused ? "Item timeline · oldest first" : "Recent item events · select an item for its timeline"}</div>
        <Table className="min-w-[1320px]" containerClassName="rounded-none border-0 shadow-none">
          <THead><TR className="whitespace-nowrap"><TH>Date</TH><TH>Event</TH><TH>Item code</TH><TH>Item name</TH><TH>Warehouse</TH>
            <TH numeric>In</TH><TH numeric>Out</TH><TH numeric>Remaining</TH>
            <TH numeric>Unit cost</TH><TH numeric>Event value</TH><TH>Source document</TH><TH>Notes</TH>
          </TR></THead>
          <TBody>{!rows.length ? <TR><TD colSpan={12} className="p-10 text-center text-slate-500">No stock events match these filters.</TD></TR>
            : rows.map(row => <TR key={row.id} className="whitespace-nowrap">
              <TD>{row.movement_date}</TD>
              <TD>{eventName(row)}</TD>
              <TD><button type="button" className="inventory-item-code rounded bg-emerald-50 px-2 py-1 font-semibold text-emerald-800 hover:bg-emerald-100" aria-label={`View history for ${row.product_code}`} onClick={() => focusItem(row)}>{row.product_code}</button></TD>
              <TD className="max-w-[230px]"><button type="button" className="block max-w-full truncate text-left text-blue-700 hover:underline" title={row.product_name} onClick={() => focusItem(row)}>{row.product_name}</button></TD>
              <TD>{row.warehouse_name}</TD>
              <TD numeric className="font-semibold text-emerald-700">{Number(row.in_quantity) ? quantity(row.in_quantity) : "—"}</TD>
              <TD numeric className="font-semibold text-rose-700">{Number(row.out_quantity) ? quantity(row.out_quantity) : "—"}</TD>
              <TD numeric className="font-bold">{row.running_quantity == null ? "—" : quantity(row.running_quantity)}</TD>
              <TD numeric>Rp {money(row.unit_cost)}</TD><TD numeric>Rp {money(row.movement_value)}</TD>
              <TD>{sourceDocuments(row)}</TD>
              <TD className="max-w-[240px]"><span className="block truncate" title={row.notes ?? undefined}>{row.notes ?? "—"}</span></TD>
            </TR>)}</TBody>
        </Table>
        <div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2 print:hidden"><label className="text-xs text-slate-600">Rows per page <select className="ml-1 rounded border border-slate-300 bg-white px-2 py-1" value={pageSize} onChange={e => setPageSize(Number(e.target.value))}><option value={50}>50</option><option value={100}>100</option></select></label><Pagination page={page} pages={pages} total={total} pageSize={pageSize} noun="events" onChange={setPage}/></div>
      </Card>
    </>}
  </div>;
}
