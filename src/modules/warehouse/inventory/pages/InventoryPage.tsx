import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Printer } from "lucide-react";
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
const input = "mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm text-slate-900";
type MovementFilter = "ALL" | "FAST" | "SLOW" | "DEAD";
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
  const initialClass = params.get("movement_class");
  const [movementClass, setMovementClass] = useState<MovementFilter>(initialClass === "FAST" || initialClass === "SLOW" || initialClass === "DEAD" ? initialClass : "ALL");
  const [pageSize, setPageSize] = useState(25);
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
    movement_class: movementClass === "ALL" ? undefined : movementClass,
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
  const hasRange = Boolean(dateFrom && movementClass === "ALL");
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

  useEffect(() => setPage(1), [search, health, accountId, movementClass, dateFrom, dateTo, pageSize]);
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);

  const changeHealth = (value: HealthFilter) => {
    setHealth(value);
    const next = new URLSearchParams(params);
    if (value === "ALL") next.delete("health");
    else next.set("health", value);
    setParams(next, { replace: true });
  };

  const changeMovement = (value: MovementFilter) => {
    setMovementClass(value);
    if (value !== "ALL") setDateFrom("");
    const next = new URLSearchParams(params);
    if (value === "ALL") next.delete("movement_class");
    else next.set("movement_class", value);
    setParams(next, { replace: true });
  };
  const movementCounts: Record<"FAST" | "SLOW" | "DEAD", { stock_lines: number; stock_value: number }> = summary.movement_classes ?? {};
  const movementDays = summary.movement_days ?? { fast: 30, dead: 90 };

  return <div className="space-y-6">
    <div className="hidden print:block">
      <h1 className="text-2xl font-bold">MMH-Connect</h1>
      <h2 className="text-xl font-semibold">Inventory</h2>
      <p className="text-xs text-slate-500">Printed {new Date().toLocaleString()}</p>
    </div>
    <div className="print:hidden">
      <PageHeader title="Inventory"
        description="Check opening and closing warehouse stock by date and inventory account."
        actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>}
      />
    </div>
    <div className="hidden print:block"><PageHeader title="Inventory" description="Warehouse stock by date and account." /></div>

    <Card className="p-4">
      <div className="grid items-end gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <label className="block min-w-0 text-xs font-medium text-slate-600">
          Search item or warehouse
          <input className={input} placeholder="Code, name or warehouse"
            value={search} onChange={e => setSearch(e.target.value)}/>
        </label>
        <label className="block min-w-0 text-xs font-medium text-slate-600">
          Inventory account
          <select className={input} value={accountId ?? ""}
            onChange={e => setAccountId(e.target.value ? Number(e.target.value) : undefined)}>
            <option value="">All inventory COA</option>
            {(accounts.data ?? []).map((account: any) =>
              <option key={account.id} value={account.id}>
                {account.account_number} — {account.account_name}
              </option>
            )}
          </select>
        </label>
        <label className="block min-w-0 text-xs font-medium text-slate-600">
          Stock status
          <select className={input} value={health}
            onChange={e => changeHealth(e.target.value as HealthFilter)}>
            <option value="ALL">All stock</option>
            <option value="HEALTHY">Healthy</option>
            <option value="LOW_STOCK">Low Stock / Reorder Required</option>
          </select>
        </label>
        <label className="block min-w-0 text-xs font-medium text-slate-600">
          Movement class
          <select className={input} value={movementClass} onChange={e => changeMovement(e.target.value as MovementFilter)}>
            <option value="ALL">All movement</option><option value="FAST">Fast</option>
            <option value="SLOW">Slow</option><option value="DEAD">Dead</option>
          </select>
        </label>
        <label className="block min-w-0 text-xs font-medium text-slate-600">
          From date
          <input type="date" className={input} value={dateFrom} disabled={movementClass !== "ALL"}
            max={dateTo || undefined} onChange={e => setDateFrom(e.target.value)}/>
        </label>
        <label className="block min-w-0 text-xs font-medium text-slate-600">
          To date
          <input type="date" className={input} value={dateTo}
            min={dateFrom || undefined} onChange={e => setDateTo(e.target.value)}/>
        </label>
      </div>
      <p className="mt-3 text-xs text-slate-500">
        {hasRange
          ? `Opening: before ${dateFrom} · Closing: ${dateTo || "current stock"} · Change: closing minus opening.`
          : `Showing stock ${dateTo ? `as of ${dateTo}` : "as of now"}. ${movementClass === "ALL" ? "Set From date to compare opening and closing balances." : "Select All movement to compare opening and closing balances."}`}
      </p>
      {invalidRange && <p className="mt-2 text-sm text-red-700">From date must be on or before To date.</p>}
    </Card>

    {!invalidRange && <>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {(["FAST", "SLOW", "DEAD"] as const).map(status => {
          const current = movementCounts[status];
          const detail = status === "FAST"
            ? `Still on hand; outbound within ${movementDays.fast} days`
            : status === "SLOW" ? `Stock active within ${movementDays.dead} days, without recent outbound`
            : `No movement for over ${movementDays.dead} days`;
          return <button type="button" key={status} onClick={() => changeMovement(movementClass === status ? "ALL" : status)}
            className={`rounded-xl border p-4 text-left shadow-sm transition hover:border-emerald-400 ${movementClass === status ? "border-emerald-500 bg-emerald-50" : "border-slate-200 bg-white"}`}>
            <div className="text-xs uppercase tracking-wide text-slate-500">{status} STOCK</div>
            <div className="mt-2 text-2xl font-bold">{current?.stock_lines ?? 0} <span className="text-sm font-normal text-slate-500">lines</span></div>
            <div className="mt-1 text-sm font-semibold">Rp {money(current?.stock_value)}</div>
            <div className="mt-1 text-xs text-slate-500">{detail}</div>
          </button>;
        })}
      </div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Closing Stock Lines</div><div className="mt-2 text-2xl font-bold">{summary.stock_lines ?? 0}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Closing Stock Value</div><div className="mt-2 text-2xl font-bold">Rp {money(summary.stock_value)}</div>{hasRange && <div className="mt-1 text-xs text-slate-500">Opening: Rp {money(openingSummary.stock_value)} · Change: Rp {money(Number(summary.stock_value ?? 0) - Number(openingSummary.stock_value ?? 0))}</div>}</Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Reorder Required at Closing</div><div className="mt-2 text-2xl font-bold text-red-700">{summary.low_stock ?? 0}</div><div className="mt-1 text-xs text-slate-500">Warehouse-item lines at or below minimum</div></Card>
      </div>

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

      <Card className="p-0">
        <div className="border-b px-4 py-3 font-semibold">Closing Totals by COA and Location</div>
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
      </Card>
      <Card className="p-0">
        {loading ? <Loading/> : <>
          <InventoryTable rows={rows}/>
          <div className="flex flex-wrap items-center justify-between gap-3 p-4">
            <label className="text-sm text-slate-600">Rows per page
              <select className="ml-2 rounded-md border border-slate-300 bg-white px-2 py-1" value={pageSize} onChange={e => setPageSize(Number(e.target.value))}>
                {[25, 50, 100].map(size => <option key={size} value={size}>{size}</option>)}
              </select>
            </label>
            <Pagination page={page} pages={pages} total={total} pageSize={pageSize} noun="stock lines" onChange={setPage}/>
          </div>
        </>}
      </Card>
    </>}
  </div>;
}
