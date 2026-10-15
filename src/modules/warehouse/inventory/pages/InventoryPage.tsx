import InventoryPrintButton from "@/components/print/InventoryPrintButton";
import { stockListReport } from "@/modules/warehouse/inventory/print/reports";
import InventoryReportHeading from "@/components/print/InventoryReportHeading";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Calculator, SlidersHorizontal } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import InventoryTable from "../components/InventoryTable";
import { useInventory } from "../useInventory";
import { inventoryApi } from "../api";

const money = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", {
  minimumFractionDigits: 2, maximumFractionDigits: 2,
});
const quantity = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", {
  maximumFractionDigits: 4,
});
const input = "mt-1 h-8 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900";
type HealthFilter = "ALL" | "HEALTHY" | "LOW_STOCK";
type AccountTotal = {
  account_id: number | null;
  account_code: string | null;
  account_name: string | null;
  quantity: number;
  stock_value: number;
};

// The opening balance is stock immediately before the selected first day.
function previousDay(value: string) {
  const day = new Date(`${value}T00:00:00Z`);
  day.setUTCDate(day.getUTCDate() - 1);
  return day.toISOString().slice(0, 10);
}

export default function InventoryPage() {
  const [params, setParams] = useSearchParams();
  const initialHealth = params.get("health") === "LOW_STOCK" ? "LOW_STOCK"
    : params.get("health") === "HEALTHY" ? "HEALTHY" : "ALL";
  const [search, setSearch] = useState("");
  const [health, setHealth] = useState<HealthFilter>(initialHealth);
  const [pageSize, setPageSize] = useState(() => Number(window.localStorage.getItem("inventory-page-size")) === 100 ? 100 : 50);
  const [showFilters, setShowFilters] = useState(false);
  const [showTotals, setShowTotals] = useState(false);
  const [accountId, setAccountId] = useState<number | undefined>();
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [page, setPage] = useState(1);

  const accounts = useQuery({
    queryKey: ["inventory-coa-filter"],
    queryFn: inventoryApi.accounts,
  });
  const filters = {
    search: search.trim() || undefined,
    health: health === "ALL" ? undefined : health,
    account_id: accountId,
  };
  const closing = useInventory({
    ...filters, page, page_size: pageSize, as_of: dateTo || undefined,
  });
  const opening = useInventory({
    ...filters, movement_class: undefined, page: 1, page_size: 1,
    as_of: dateFrom ? previousDay(dateFrom) : undefined,
  });

  const data: any = closing.data ?? {};
  const openingData: any = opening.data ?? {};
  const rows: any[] = data.items ?? [];
  const summary = data.summary ?? {};
  const openingSummary = openingData.summary ?? {};
  const accountLocationTotals: any[] = data.totals_by_account_location ?? [];
  const accountTotals: AccountTotal[] = data.totals_by_account ?? [];
  const openingTotals: AccountTotal[] = openingData.totals_by_account ?? [];
  const pages = Math.max(data.total_pages ?? 0, 1);
  const total = data.total_items ?? 0;
  const hasRange = Boolean(dateFrom);
  const loading = closing.isFetching || (hasRange && opening.isFetching);
  const invalidRange = Boolean(dateFrom && dateTo && dateFrom > dateTo);

  const rangeTotals = (() => {
    const byId = new Map<string, { closing?: AccountTotal; opening?: AccountTotal }>();
    for (const row of accountTotals) {
      const key = String(row.account_id ?? "unmapped");
      byId.set(key, { ...byId.get(key), closing: row });
    }
    for (const row of openingTotals) {
      const key = String(row.account_id ?? "unmapped");
      byId.set(key, { ...byId.get(key), opening: row });
    }
    return [...byId.values()].sort((a, b) =>
      (a.closing?.account_code ?? a.opening?.account_code ?? "").localeCompare(
        b.closing?.account_code ?? b.opening?.account_code ?? ""
      )
    );
  })();

  useEffect(() => setPage(1), [search, health, accountId, dateFrom, dateTo, pageSize]);
  useEffect(() => window.localStorage.setItem("inventory-page-size", String(pageSize)), [pageSize]);
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);

  const changeHealth = (value: HealthFilter) => {
    setHealth(value);
    const next = new URLSearchParams(params);
    if (value === "ALL") next.delete("health");
    else next.set("health", value);
    setParams(next, { replace: true });
  };


  return <div className="inventory-print-report space-y-2">
    <InventoryReportHeading title={"Inventory"} context={`Period: ${dateFrom || "2026-01-01"} – ${dateTo || "Current"}${search ? ` · Search: ${search}` : ""}${accountId ? ` · Account ID: ${accountId}` : ""} · Health: ${health}`} rows={rows.length} total={total}/>
    <div className="print:hidden">
      <PageHeader title="Inventory"
        description="Check opening and closing warehouse stock by date and inventory account."
        actions={<InventoryPrintButton loadReport={() => stockListReport({...filters,as_of:dateTo || undefined}, `As of: ${dateTo || "Current"}${dateFrom ? ` · From: ${dateFrom}` : ""} · Search: ${search || "All"} · Health: ${health}${accountId ? ` · Account: ${accounts.data?.find(a => a.id === accountId)?.account_name || accountId}` : ""}`)}/>}
      />
    </div>


    <Card className="p-2 print:hidden">
      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[220px] flex-1">        <label className="block min-w-0 text-xs font-medium text-slate-600">
          <span className="sr-only">Search item or warehouse</span>
          <input className={input} placeholder="Code, name or warehouse"
            value={search} onChange={e => setSearch(e.target.value)}/>
        </label>
</div>
        <Button type="button" size="sm" variant="outline" title="Filters" aria-label="Filters" aria-expanded={showFilters} onClick={() => setShowFilters(value => !value)}>
          <SlidersHorizontal size={15}/>
        </Button>
      </div>
      {showFilters && <div className="mt-2 grid gap-2 border-t border-slate-100 pt-2 sm:grid-cols-2 xl:grid-cols-4">        <label className="text-xs font-medium text-slate-600">Stock status
          <select className={input} value={health} onChange={e => changeHealth(e.target.value as HealthFilter)}>
            <option value="ALL">All stock</option><option value="HEALTHY">Healthy</option><option value="LOW_STOCK">Low stock</option>
          </select>
        </label>

        <label className="block min-w-0 text-xs font-medium text-slate-600">Inventory account
          <select className={input} value={accountId ?? ""} onChange={e => setAccountId(e.target.value ? Number(e.target.value) : undefined)}>
            <option value="">All inventory COA</option>
            {(accounts.data ?? []).map((account: any) => <option key={account.id} value={account.id}>{account.account_number} — {account.account_name}</option>)}
          </select>
        </label>
        <label className="block min-w-0 text-xs font-medium text-slate-600">From date
          <input type="date" className={input} value={dateFrom} max={dateTo || undefined} onChange={e => setDateFrom(e.target.value)}/>
        </label>
        <label className="block min-w-0 text-xs font-medium text-slate-600">To date
          <input type="date" className={input} value={dateTo} min={dateFrom || undefined} onChange={e => setDateTo(e.target.value)}/>
        </label>
      </div>}
      {invalidRange && <p className="mt-2 text-sm text-red-700">From date must be on or before To date.</p>}
    </Card>

    {!invalidRange && <>
      <div className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded border bg-white px-2 py-1 text-xs"><span>Stock lines <b>{summary.stock_lines ?? 0}</b></span><span>Value <b>Rp {money(summary.stock_value)}</b></span><span>Reorder <b className="text-red-700">{summary.low_stock ?? 0}</b></span>{hasRange && <span>Opening Rp {money(openingSummary.stock_value)} · Change Rp {money(Number(summary.stock_value ?? 0)-Number(openingSummary.stock_value ?? 0))}</span>}<Button variant="outline" size="xs" title="Account totals" aria-label="Account totals" aria-expanded={showTotals} onClick={()=>setShowTotals(v=>!v)}><Calculator size={14}/></Button></div>
      {showTotals && <>
      <Card className="p-0">
        <div className="border-b px-4 py-3 font-semibold">Totals by Inventory Account {dateTo ? `as of ${dateTo}` : "(current)"}</div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead><tr>
              <th className="px-4 py-2 text-left">Inventory COA</th>
              {hasRange && <th className="px-4 py-2 text-right">Opening Qty</th>}
              <th className="px-4 py-2 text-right">Closing Qty</th>
              {hasRange && <th className="px-4 py-2 text-right">Change</th>}
              <th className="px-4 py-2 text-right">Closing Value</th>
            </tr></thead>
            <tbody>
              {(hasRange ? rangeTotals : accountTotals.map(closingRow => ({ closing: closingRow }))).map(row => {
                const closingRow = row.closing;
                const openingRow = "opening" in row ? row.opening : undefined;
                const id = closingRow?.account_id ?? openingRow?.account_id ?? "none";
                return <tr key={id} className="border-t">
                  <td className="px-4 py-2">{closingRow?.account_code ?? openingRow?.account_code
                    ? `${closingRow?.account_code ?? openingRow?.account_code} — ${closingRow?.account_name ?? openingRow?.account_name}`
                    : "Unmapped"}</td>
                  {hasRange && <td className="px-4 py-2 text-right">{quantity(openingRow?.quantity)}</td>}
                  <td className="px-4 py-2 text-right">{quantity(closingRow?.quantity)}</td>
                  {hasRange && <td className="px-4 py-2 text-right">{quantity(Number(closingRow?.quantity ?? 0) - Number(openingRow?.quantity ?? 0))}</td>}
                  <td className="px-4 py-2 text-right">Rp {money(closingRow?.stock_value)}</td>
                </tr>;
              })}
              {!accountTotals.length && !openingTotals.length && !loading &&
                <tr className="border-t"><td colSpan={hasRange ? 5 : 3} className="px-4 py-6 text-center text-slate-500">No stock for the selected filters.</td></tr>}
            </tbody>
          </table>
        </div>
      </Card>

      <details className="rounded-lg border border-slate-200 bg-white"><summary className="cursor-pointer px-4 py-2 text-sm font-semibold">Closing totals by COA and location</summary>
        <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-sm">
          <thead><tr><th className="px-4 py-2 text-left">COA</th><th className="px-4 py-2 text-left">Location</th><th className="px-4 py-2 text-right">Quantity</th><th className="px-4 py-2 text-right">Stock Value</th></tr></thead>
          <tbody>{accountLocationTotals.map((row: any) =>
            <tr key={`${row.account_id ?? "none"}-${row.location_id ?? "none"}`} className="border-t">
              <td className="px-4 py-2">{row.account_code ? `${row.account_code} — ${row.account_name}` : "Unmapped"}</td>
              <td className="px-4 py-2">{row.location_name ?? "Unassigned"}</td>
              <td className="px-4 py-2 text-right">{quantity(row.quantity)}</td>
              <td className="px-4 py-2 text-right">Rp {money(row.stock_value)}</td>
            </tr>
          )}
          {!accountLocationTotals.length && !loading &&
            <tr className="border-t"><td colSpan={4} className="px-4 py-6 text-center text-slate-500">No stock totals for the selected filters.</td></tr>}
          </tbody>
        </table></div>
      </details>
      </>}
      <Card className="p-0">
        {loading ? <Loading/> : <>
          <InventoryTable rows={rows}/>
          <div className="flex flex-wrap items-center justify-between gap-3 p-4 print:hidden">
            <label className="text-sm text-slate-600">Rows per page
              <select className="ml-2 rounded-md border border-slate-300 bg-white px-2 py-1" value={pageSize} onChange={e => setPageSize(Number(e.target.value))}>
                {[50, 100].map(size => <option key={size} value={size}>{size}</option>)}
              </select>
            </label>
            <Pagination page={page} pages={pages} total={total} pageSize={pageSize} noun="stock lines" onChange={setPage}/>
          </div>
        </>}
      </Card>
    </>}
  </div>;
}
