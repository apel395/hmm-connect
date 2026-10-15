import {
  cloneElement,
  useEffect,
  useRef,
  useState,
  type ReactElement,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";
import {
  ArrowDownUp,
  ArrowUpRight,
  Boxes,
  Calculator,
  ChevronLeft,
  ChevronRight,
  Columns3,
  ListFilter,
  RefreshCw,
  Search,
  SlidersHorizontal,
  X,
} from "lucide-react";
import { toast } from "sonner";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import InventoryPrintButton from "@/components/print/InventoryPrintButton";
import InventoryReportHeading from "@/components/print/InventoryReportHeading";
import { stockListReport } from "../print/reports";
import InventoryTable from "../components/InventoryTable";
import {
  STOCK_COLUMNS,
  type StockColumn,
} from "../components/stockTableSettings";
import { useInventory } from "../useInventory";
import { inventoryApi } from "../api";
import type { Inventory } from "../types";
import { useWarehouses } from "@/modules/master/warehouses/hooks/useWarehouses";

const money = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
const qty = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });
const id = (value: string | null) =>
  value && /^\d+$/.test(value) && Number(value) > 0 ? Number(value) : undefined;
const previousDay = (value: string) => {
  const d = new Date(`${value}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() - 1);
  return d.toISOString().slice(0, 10);
};
const field = "stock-filter-field";
type AccountTotal = {
  account_id: number | null;
  account_code: string | null;
  account_name: string | null;
  stock_value: number;
  location_id?: number;
  location_name?: string;
};
type Result = {
  items: Inventory[];
  summary: { stock_lines?: number; stock_value?: number; low_stock?: number };
  total_items: number;
  total_pages: number;
  totals_by_account?: AccountTotal[];
  totals_by_account_location?: AccountTotal[];
};
const defaultColumns = STOCK_COLUMNS.map((column) => column.id);
function savedColumns(): StockColumn[] {
  try {
    const saved = JSON.parse(
      window.localStorage.getItem("mmh-stock-columns-v1") ?? "null",
    );
    return Array.isArray(saved)
      ? defaultColumns.filter((c) => saved.includes(c))
      : defaultColumns;
  } catch {
    return defaultColumns;
  }
}

export default function InventoryPage() {
  const [params, setParams] = useSearchParams();
  // Merge rapid changes against the latest requested URL, until navigation commits.
  const pendingParams = useRef<URLSearchParams | null>(null);
  useEffect(() => {
    if (pendingParams.current?.toString() === params.toString())
      pendingParams.current = null;
  }, [params]);
  const searchParam = params.get("search") ?? "";
  const [search, setSearch] = useState(searchParam);
  const [showFilters, setShowFilters] = useState(false),
    [showColumns, setShowColumns] = useState(false),
    [showTotals, setShowTotals] = useState(false),
    [byLocation, setByLocation] = useState(false);
  const [selected, setSelected] = useState<Inventory | null>(null);
  const [columns, setColumns] = useState<StockColumn[]>(savedColumns);
  const [compact, setCompact] = useState(
    () => window.localStorage.getItem("mmh-stock-density") === "dense",
  );
  const searchRef = useRef<HTMLInputElement>(null),
    columnsRef = useRef<HTMLDivElement>(null);
  const accountId = id(params.get("account_id")),
    warehouseId = id(params.get("warehouse_id"));
  const health =
    params.get("health") === "LOW_STOCK"
      ? "LOW_STOCK"
      : params.get("health") === "HEALTHY"
        ? "HEALTHY"
        : undefined;
  const dateFrom = params.get("date_from") ?? "",
    dateTo = params.get("date_to") ?? "";
  const page = id(params.get("page")) ?? 1;
  const pageSize =
    params.get("page_size") === "100"
      ? 100
      : params.get("page_size") === "50"
        ? 50
        : Number(window.localStorage.getItem("inventory-page-size")) === 100
          ? 100
          : 50;
  const validDate = (value: string) =>
    !value ||
    (/^\d{4}-\d{2}-\d{2}$/.test(value) &&
      !Number.isNaN(new Date(`${value}T00:00:00Z`).getTime()) &&
      new Date(`${value}T00:00:00Z`).toISOString().slice(0, 10) === value);
  const invalidRange =
    !validDate(dateFrom) ||
    !validDate(dateTo) ||
    Boolean(dateFrom && dateTo && dateFrom > dateTo);
  const update = (values: Record<string, string | undefined>) => {
    const next = new URLSearchParams(pendingParams.current ?? params);
    next.delete("page");
    for (const [key, value] of Object.entries(values)) {
      if (value) next.set(key, value);
      else next.delete(key);
    }
    pendingParams.current = next;
    setParams(next, { replace: true });
  };
  useEffect(() => setSearch(searchParam), [searchParam]);
  useEffect(() => {
    if (search.trim() === searchParam) return;
    const timer = setTimeout(() => {
      const next = new URLSearchParams(pendingParams.current ?? params);
      if (search.trim()) next.set("search", search.trim());
      else next.delete("search");
      next.delete("page");
      pendingParams.current = next;
      setParams(next, { replace: true });
    }, 250);
    return () => clearTimeout(timer);
  }, [search, searchParam, params, setParams]);
  useEffect(() => {
    window.localStorage.setItem(
      "mmh-stock-columns-v1",
      JSON.stringify(columns),
    );
  }, [columns]);
  useEffect(() => {
    window.localStorage.setItem(
      "mmh-stock-density",
      compact ? "dense" : "comfortable",
    );
  }, [compact]);
  useEffect(() => {
    if (!showColumns) return;
    const close = (event: MouseEvent) => {
      if (!columnsRef.current?.contains(event.target as Node))
        setShowColumns(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setShowColumns(false);
    };
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", escape);
    };
  }, [showColumns]);
  const accounts = useQuery({
    queryKey: ["inventory-coa-filter"],
    queryFn: inventoryApi.accounts,
  });
  const warehouses = useWarehouses();
  const filters: import("../api").InventoryListParams = {
    search: searchParam || undefined,
    health,
    account_id: accountId,
    warehouse_id: warehouseId,
  };
  const closing = useInventory(
    { ...filters, page, page_size: pageSize, as_of: dateTo || undefined },
    { enabled: !invalidRange },
  );
  const opening = useInventory(
    {
      ...filters,
      page: 1,
      page_size: 1,
      as_of: dateFrom && !invalidRange ? previousDay(dateFrom) : undefined,
    },
    { enabled: !!dateFrom && !invalidRange },
  );
  const data = closing.data as Result | undefined,
    openingData = opening.data as Result | undefined;
  const rows = data?.items ?? [],
    total = data?.total_items ?? 0,
    pages = Math.max(data?.total_pages ?? 0, 1),
    summary = data?.summary;
  const hasOpening =
    !!dateFrom &&
    !!openingData &&
    !opening.isError &&
    !opening.isPlaceholderData;
  const fetching = closing.isFetching || (!!dateFrom && opening.isFetching);
  const account = accounts.data?.find((row) => row.id === accountId),
    warehouse = warehouses.data?.find((row) => row.id === warehouseId);
  const activeFilters = [
    accountId
      ? { key: "account_id", label: account?.account_name ?? "Account" }
      : null,
    warehouseId
      ? { key: "warehouse_id", label: warehouse?.name ?? "Warehouse" }
      : null,
    health
      ? {
          key: "health",
          label: health === "LOW_STOCK" ? "Reorder needed" : "Healthy stock",
        }
      : null,
    dateFrom ? { key: "date_from", label: `From ${dateFrom}` } : null,
    dateTo ? { key: "date_to", label: `To ${dateTo}` } : null,
  ].filter((f): f is { key: string; label: string } => !!f);
  const comparison = new Map<
    string,
    { opening?: AccountTotal; closing?: AccountTotal }
  >();
  for (const row of data?.totals_by_account ?? [])
    comparison.set(String(row.account_id ?? "unmapped"), { closing: row });
  for (const row of hasOpening ? (openingData?.totals_by_account ?? []) : []) {
    const key = String(row.account_id ?? "unmapped");
    comparison.set(key, { ...comparison.get(key), opening: row });
  }
  const context = `${dateTo ? `As of ${dateTo}` : "Current stock"}${dateFrom ? ` · From ${dateFrom}` : ""} · Search: ${searchParam || "All"} · ${warehouse?.name ?? "All accessible warehouses"}${account ? ` · ${account.account_number} ${account.account_name}` : ""}${health ? ` · ${health}` : ""}`;
  const refresh = async () => {
    const results = await Promise.all([
      closing.refetch(),
      ...(dateFrom ? [opening.refetch()] : []),
    ]);
    if (results.some((result) => result.isError))
      toast.error("Unable to refresh inventory");
  };
  const filterField = (
    label: string,
    content: ReactElement<{ "aria-label"?: string }>,
  ) => (
    <label className="stock-filter-label">
      {label}
      {cloneElement(content, { "aria-label": label })}
    </label>
  );
  const changePage = (value: number) => {
    const next = new URLSearchParams(pendingParams.current ?? params);
    next.set("page", String(value));
    pendingParams.current = next;
    setParams(next, { replace: true });
    setSelected(null);
  };
  return (
    <section className="inventory-workspace inventory-print-report">
      <InventoryReportHeading
        title="Inventory"
        context={context}
        rows={rows.length}
        total={total}
      />
      <div className="stock-page-heading print:hidden">
        <div className="flex min-w-0 items-center gap-3">
          <div className="stock-module-mark">
            <Boxes size={21} strokeWidth={1.7} />
          </div>
          <div>
            <div className="stock-eyebrow">WAREHOUSE OPERATIONS</div>
            <h1>Inventory</h1>
          </div>
          <span className="stock-record-count">
            {data ? total.toLocaleString("id-ID") : "…"} stock lines
          </span>
        </div>
        <Link className="stock-secondary-link" to="/inventory/movements">
          <ArrowDownUp size={14} />
          <span>Stock movements</span>
          <ArrowUpRight size={13} />
        </Link>
      </div>
      <div className="stock-workbench">
        <div className="stock-toolbar print:hidden">
          <div
            className="stock-view-switch"
            role="group"
            aria-label="Stock view"
          >
            <button
              type="button"
              data-active={!health}
              onClick={() => update({ health: undefined })}
            >
              All stock
            </button>
            <button
              type="button"
              data-active={health === "LOW_STOCK"}
              onClick={() => update({ health: "LOW_STOCK" })}
            >
              Reorder
              {summary?.low_stock !== undefined &&
                (!health || health === "LOW_STOCK") && (
                  <span>{summary.low_stock}</span>
                )}
            </button>
          </div>
          <div className="stock-search">
            <Search size={15} />
            <input
              data-form-control
              ref={searchRef}
              aria-label="Search item or warehouse"
              placeholder="Search code, item or warehouse…"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            {search && (
              <button
                title="Clear search"
                aria-label="Clear search"
                onClick={() => {
                  setSearch("");
                  update({ search: undefined });
                  searchRef.current?.focus();
                }}
              >
                <X size={13} />
              </button>
            )}
          </div>
          <div className="stock-tools">
            <button
              className="stock-tool"
              data-active={showFilters || !!activeFilters.length}
              title="Filters"
              aria-label="Filters"
              aria-expanded={showFilters}
              onClick={() => setShowFilters((v) => !v)}
            >
              <SlidersHorizontal size={16} />
              {!!activeFilters.length && <b>{activeFilters.length}</b>}
            </button>
            <span className="stock-tool-divider" />
            <button
              className="stock-tool"
              title="Account totals"
              aria-label="Account totals"
              disabled={!data || invalidRange}
              onClick={() => setShowTotals(true)}
            >
              <Calculator size={16} />
            </button>
            <div className="relative" ref={columnsRef}>
              <button
                className="stock-tool"
                title="Table settings"
                aria-label="Table settings"
                aria-expanded={showColumns}
                onClick={() => setShowColumns((v) => !v)}
              >
                <Columns3 size={16} />
              </button>
              {showColumns && (
                <div className="stock-column-menu">
                  <strong>Table settings</strong>
                  <span className="stock-menu-caption">Visible columns</span>
                  <div className="px-2 py-1 text-xs text-slate-400">
                    Item code and name stay visible
                  </div>
                  {STOCK_COLUMNS.map((column) => (
                    <label key={column.id}>
                      <input
                        type="checkbox"
                        checked={columns.includes(column.id)}
                        onChange={(event) =>
                          setColumns((old) =>
                            event.target.checked
                              ? defaultColumns.filter(
                                  (key) =>
                                    key === column.id || old.includes(key),
                                )
                              : old.filter((key) => key !== column.id),
                          )
                        }
                      />
                      {column.label}
                    </label>
                  ))}
                  <div className="stock-menu-separator" />
                  <label>
                    <input
                      type="checkbox"
                      checked={compact}
                      onChange={(e) => setCompact(e.target.checked)}
                    />
                    Extra compact rows
                  </label>
                  <button
                    className="stock-menu-reset"
                    onClick={() => {
                      setColumns(defaultColumns);
                      setCompact(false);
                    }}
                  >
                    Reset table layout
                  </button>
                </div>
              )}
            </div>
            <button
              className="stock-tool"
              title="Refresh inventory"
              aria-label="Refresh inventory"
              disabled={fetching || invalidRange}
              onClick={() => void refresh()}
            >
              <RefreshCw size={15} className={fetching ? "animate-spin" : ""} />
            </button>
            <InventoryPrintButton
              disabled={invalidRange || !data}
              loadReport={() =>
                stockListReport(
                  { ...filters, as_of: dateTo || undefined },
                  context,
                )
              }
            />
          </div>
        </div>
        {showFilters && (
          <div className="stock-filter-panel print:hidden">
            {filterField(
              "Warehouse",
              <select
                data-form-control
                className={field}
                value={warehouseId ?? ""}
                onChange={(e) => update({ warehouse_id: e.target.value })}
              >
                <option value="">All accessible warehouses</option>
                {warehouses.data
                  ?.filter((row) => row.is_active)
                  .map((row) => (
                    <option key={row.id} value={row.id}>
                      {row.name} · {row.code}
                    </option>
                  ))}
              </select>,
            )}
            {filterField(
              "Inventory account",
              <select
                data-form-control
                className={field}
                value={accountId ?? ""}
                onChange={(e) => update({ account_id: e.target.value })}
              >
                <option value="">All inventory accounts</option>
                {accounts.data?.map((row) => (
                  <option key={row.id} value={row.id}>
                    {row.account_number} · {row.account_name}
                  </option>
                ))}
              </select>,
            )}
            {filterField(
              "From date",
              <input
                data-form-control
                className={field}
                type="date"
                min="2026-01-01"
                max={dateTo || undefined}
                value={dateFrom}
                onChange={(e) => update({ date_from: e.target.value })}
              />,
            )}
            {filterField(
              "To date",
              <input
                data-form-control
                className={field}
                type="date"
                min={dateFrom || "2026-01-01"}
                value={dateTo}
                onChange={(e) => update({ date_to: e.target.value })}
              />,
            )}
            <button
              className="stock-filter-clear"
              onClick={() =>
                update({
                  warehouse_id: undefined,
                  account_id: undefined,
                  health: undefined,
                  date_from: undefined,
                  date_to: undefined,
                })
              }
            >
              Reset filters
            </button>
          </div>
        )}
        {!!activeFilters.length && (
          <div className="stock-filter-chips print:hidden">
            <ListFilter size={13} />
            {activeFilters.map((f) => (
              <button
                key={f.key}
                title={`Remove ${f.label} filter`}
                onClick={() => update({ [f.key]: undefined })}
              >
                {f.label}
                <X size={11} />
              </button>
            ))}
            <button
              className="stock-clear-all"
              onClick={() =>
                update({
                  warehouse_id: undefined,
                  account_id: undefined,
                  health: undefined,
                  date_from: undefined,
                  date_to: undefined,
                })
              }
            >
              Clear all
            </button>
          </div>
        )}
        <div className="stock-summary-strip">
          <span>{warehouse?.name ?? "All accessible warehouses"}</span>
          <span className="stock-summary-period">
            {dateTo ? `As of ${dateTo}` : "Current stock"}
          </span>
          <div className="stock-summary-values">
            <span>
              Stock value{" "}
              <strong>
                {data ? `Rp ${money(summary?.stock_value)}` : "—"}
              </strong>
            </span>
            {hasOpening && openingData && (
              <span>
                Opening{" "}
                <strong>Rp {money(openingData.summary.stock_value)}</strong>
              </span>
            )}
          </div>
        </div>
        {invalidRange ? (
          <div role="alert" className="stock-state-message text-red-700">
            Choose a valid date range. From date must be on or before To date.
          </div>
        ) : closing.isError ? (
          <div role="alert" className="stock-state-message">
            <strong>Inventory could not be loaded</strong>
            <button onClick={() => void refresh()}>Try again</button>
          </div>
        ) : !data ? (
          <div role="status" className="stock-state-message">
            <RefreshCw className="animate-spin text-emerald-700" size={22} />
            Loading warehouse stock…
          </div>
        ) : (
          <div className="stock-table-region" aria-busy={fetching}>
            {fetching && <div className="stock-fetch-bar" />}
            <InventoryTable
              rows={rows}
              columns={columns}
              compact={compact}
              selectedId={selected?.id}
              onSelect={setSelected}
            />
          </div>
        )}
        <footer className="stock-footer print:hidden">
          <div>
            <span className="stock-footer-range">
              {total
                ? `${Math.min((page - 1) * pageSize + 1, total)}–${Math.min(page * pageSize, total)}`
                : "0"}
            </span>{" "}
            of {total.toLocaleString("id-ID")} stock lines
          </div>
          <div className="stock-footer-right">
            <label>
              Rows
              <select
                data-form-control
                aria-label="Rows per page"
                value={pageSize}
                onChange={(e) => {
                  window.localStorage.setItem(
                    "inventory-page-size",
                    e.target.value,
                  );
                  update({ page_size: e.target.value });
                }}
              >
                <option>50</option>
                <option>100</option>
              </select>
            </label>
            <div className="stock-pagination">
              <button
                title="Previous page"
                aria-label="Previous page"
                disabled={page <= 1 || fetching}
                onClick={() => changePage(page - 1)}
              >
                <ChevronLeft size={15} />
              </button>
              <span>
                {page} / {pages}
              </span>
              <button
                title="Next page"
                aria-label="Next page"
                disabled={page >= pages || fetching}
                onClick={() => changePage(page + 1)}
              >
                <ChevronRight size={15} />
              </button>
            </div>
          </div>
        </footer>
      </div>
      <Dialog
        open={!!selected}
        onOpenChange={(open) => {
          if (!open) setSelected(null);
        }}
      >
        <DialogContent className="stock-side-panel">
          <DialogHeader>
            <div className="stock-eyebrow">ITEM OVERVIEW</div>
            <DialogTitle className="mt-1 pr-5 text-base font-semibold">
              {selected?.product_name}
            </DialogTitle>
            <div className="mt-1 font-mono text-xs text-emerald-700">
              {selected?.product_code}
            </div>
          </DialogHeader>
          {selected && (
            <DialogBody>
              <div className="stock-detail-balance">
                <span>On hand</span>
                <strong>
                  {qty(selected.quantity)} <small>{selected.uom}</small>
                </strong>
                <span>
                  {selected.warehouse_name} · {selected.warehouse_code}
                </span>
              </div>
              <dl className="stock-detail-fields">
                <div>
                  <dt>Average cost</dt>
                  <dd>Rp {money(selected.average_cost)}</dd>
                </div>
                <div>
                  <dt>Stock value</dt>
                  <dd>Rp {money(selected.stock_value)}</dd>
                </div>
                <div>
                  <dt>Minimum stock</dt>
                  <dd>
                    {qty(selected.minimum_stock)} {selected.uom}
                  </dd>
                </div>
                <div>
                  <dt>Reorder needed</dt>
                  <dd>
                    {selected.low_stock || selected.needs_reorder
                      ? "Yes"
                      : "No"}
                  </dd>
                </div>
              </dl>
              <Link
                onClick={() => setSelected(null)}
                className="stock-detail-action"
                to={`/inventory/movements?product_id=${selected.product_id}&warehouse_id=${selected.warehouse_id}`}
              >
                <ArrowDownUp size={15} />
                View stock card
                <ArrowUpRight size={14} />
              </Link>
            </DialogBody>
          )}
        </DialogContent>
      </Dialog>
      <Dialog open={showTotals} onOpenChange={setShowTotals}>
        <DialogContent className="stock-side-panel">
          <DialogHeader>
            <div className="stock-eyebrow">VALUATION</div>
            <DialogTitle className="mt-1 text-base font-semibold">
              Account totals
            </DialogTitle>
          </DialogHeader>
          <DialogBody>
            <div className="stock-detail-balance">
              <span>
                {dateTo ? `Stock value as of ${dateTo}` : "Current stock value"}
              </span>
              <strong className="!text-2xl">
                Rp {money(summary?.stock_value)}
              </strong>
              <span>{warehouse?.name ?? "All accessible warehouses"}</span>
            </div>
            <div className="stock-breakdown-tabs">
              <button
                data-active={!byLocation}
                onClick={() => setByLocation(false)}
              >
                By account
              </button>
              <button
                data-active={byLocation}
                onClick={() => setByLocation(true)}
              >
                By location
              </button>
            </div>
            {byLocation
              ? (data?.totals_by_account_location ?? []).map((row) => (
                  <div
                    key={`${row.account_id}-${row.location_id}`}
                    className="stock-account-total"
                  >
                    <div>
                      <span>{row.account_name ?? "Unmapped"}</span>
                      <small>
                        {row.location_name ?? "Unassigned location"}
                      </small>
                    </div>
                    <strong>Rp {money(row.stock_value)}</strong>
                  </div>
                ))
              : [...comparison.entries()].map(([key, row]) => (
                  <div className="stock-account-total" key={key}>
                    <div>
                      <span>
                        {row.closing?.account_name ??
                          row.opening?.account_name ??
                          "Unmapped"}
                      </span>
                      <small>
                        {row.closing?.account_code ??
                          row.opening?.account_code ??
                          "No account mapping"}
                      </small>
                      {hasOpening && (
                        <small>
                          Opening Rp {money(row.opening?.stock_value)}
                        </small>
                      )}
                    </div>
                    <strong>Rp {money(row.closing?.stock_value)}</strong>
                  </div>
                ))}
          </DialogBody>
        </DialogContent>
      </Dialog>
    </section>
  );
}
