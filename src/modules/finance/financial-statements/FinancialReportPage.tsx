import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Download, ListFilter, RefreshCw, Settings2 } from "lucide-react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import DepartmentPerformanceTable, { type DepartmentPerformance } from "./DepartmentPerformanceTable";
import api from "@/api/client";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { listBusinessUnits, listLocations, listDepartments } from "@/modules/admin/organization/api";
import useAuthStore from "@/store/auth";

export type Kind = "PROFIT_LOSS" | "BALANCE_SHEET";
export type Period = "MTD" | "YTD";
export type Amounts = { current: string; budget: string | null; last_month: string | null; last_year: string | null; variance: string | null; movement?: string };
export type Row = { account_code: string; account_name: string; account_ids: number[]; section: string; periods: Record<Period, Amounts> };
export type Report = { departments?: DepartmentPerformance[]; rows: Row[]; header_only: boolean; section_totals: Record<string, Record<Period, Amounts>>; budget_available: Record<Period, boolean>; comparison_available?: Record<Period, Partial<Record<keyof Amounts, boolean>>>; scope_labels?: Record<string, string>; scope: { location_id: number | null; business_unit_id: number | null; department_id: number | null }; periods: Record<Period, Record<string, string[]>> };
const money = (value: string | number | null | undefined) => value == null ? "—" : Number(value).toLocaleString("id-ID", { maximumFractionDigits: 2 });
const input = "h-8 rounded border border-slate-300 bg-white px-2 text-xs";
const labels: Record<string, string> = { REVENUE: "Pendapatan", COST_OF_REVENUE: "Beban pokok", EXPENSES: "Beban", ASSETS: "Aset", LIABILITIES: "Liabilitas", EQUITY: "Ekuitas" };
const metrics = ["current", "budget", "last_month", "last_year", "variance"] as const;
const metricNames = ["Current", "Budget", "Last month", "Last year", "Variance"];
const initial = { as_of_date: new Date().toLocaleDateString("en-CA"), business_unit_id: "", location_id: "", department_id: "", budget_id: "", kap: false, include_zero: false };

export default function FinancialReportPage({ kind }: { kind: Kind }) {
  const user = useAuthStore(state => state.user);
  const canManage = useAuthStore(state => state.hasPermission("finance.manage"));
  const initialFilters = () => {
    const query = new URLSearchParams(window.location.search);
    return { ...initial, as_of_date: query.get("as_of_date") || initial.as_of_date,
      location_id: query.get("location_id") || "", business_unit_id: query.get("business_unit_id") || "", department_id: query.get("department_id") || "" };
  };
  const [draft, setDraft] = useState(initialFilters);
  const [filters, setFilters] = useState(initialFilters);
  const [showFilters, setShowFilters] = useState(false);
  const [period, setPeriod] = useState<Period>("MTD");
  const params = Object.fromEntries(Object.entries({ ...filters, report_type: kind }).filter(([, value]) => value !== ""));
  const report = useQuery({ queryKey: ["financial-report-comparison", kind, filters], queryFn: async () => (await api.get<Report>("/financial-reports/comparison", { params })).data });
  const units = useQuery({ queryKey: ["report-units"], queryFn: listBusinessUnits, enabled: showFilters });
  const locations = useQuery({ queryKey: ["report-locations", draft.business_unit_id], queryFn: () => listLocations({ is_active: true, business_unit_id: Number(draft.business_unit_id) || undefined }), enabled: showFilters });
  const departments = useQuery({ queryKey: ["report-departments", draft.business_unit_id], queryFn: () => listDepartments({ is_active: true, business_unit_id: Number(draft.business_unit_id) || undefined }), enabled: showFilters });
  const budgets = useQuery({ queryKey: ["report-budgets", draft.as_of_date.slice(0, 4)], queryFn: async () => (await api.get("/budgets", { params: { fiscal_year: draft.as_of_date.slice(0, 4), page_size: 500 } })).data, enabled: showFilters });
  const title = kind === "PROFIT_LOSS" ? "Profit & Loss" : "Balance Sheet";
  const data = report.data;
  const scopeNames = data ? Object.entries(data.scope).filter(([, value]) => value != null).map(([key]) => data.scope_labels?.[key]).filter(Boolean) : [];
  const error = report.error as { response?: { data?: { detail?: string } } } | null;
  const exportReport = async () => {
    try {
      const response = await api.get("/financial-reports/comparison/export", { params, responseType: "blob" });
      const url = URL.createObjectURL(response.data);
      const link = document.createElement("a"); link.href = url; link.download = `${kind.toLowerCase()}-${filters.as_of_date}.xlsx`; link.click(); URL.revokeObjectURL(url);
    } catch { toast.error("Export could not be completed"); }
  };
  const ledgerLink = (row: Row) => {
    if (!row.account_ids.length) {
      const query = new URLSearchParams({ as_of_date: filters.as_of_date });
      for (const name of ["location_id", "business_unit_id", "department_id"] as const) if (data?.scope[name]) query.set(name, String(data.scope[name]));
      return `/profit-loss?${query}`;
    }
    const query = new URLSearchParams({ date_from: `${filters.as_of_date.slice(0, 4)}-${period === "YTD" ? "01" : filters.as_of_date.slice(5, 7)}-01`, date_to: filters.as_of_date });
    if (row.account_ids.length === 1) query.set("account_id", String(row.account_ids[0]));
    else query.set("account_ids", row.account_ids.join(","));
    for (const name of ["location_id", "business_unit_id", "department_id"] as const) if (data?.scope[name]) query.set(name, String(data.scope[name]));
    return `/general-ledger?${query}`;
  };
  const totals = (section: string) => data?.section_totals[section]?.[period];
  const profit = data ? metrics.map(metric => {
    const r = totals("REVENUE")?.[metric], c = totals("COST_OF_REVENUE")?.[metric], e = totals("EXPENSES")?.[metric];
    return r == null || c == null || e == null ? null : Number(r) - Number(c) - Number(e);
  }) : [];
  const columns = kind === "BALANCE_SHEET" ? [...metrics, "movement" as const] : [...metrics];
  const headings = kind === "BALANCE_SHEET" ? [...metricNames, "Movement"] : metricNames;
  const table = (sections: string[]) => <div className="overflow-x-auto rounded border bg-white"><table className="w-full text-xs whitespace-nowrap"><thead className="bg-slate-100"><tr><th className="px-2 py-1.5 text-left">Account</th>{headings.map((name, index) => <th title={data?.comparison_available?.[period][columns[index]] === false ? "Comparison data unavailable for this year and scope" : data?.periods[period][columns[index]]?.join(" to ")} key={name} className="px-2 py-1.5 text-right">{name}</th>)}</tr></thead><tbody>
    {sections.map(section => <ReportSection key={section} section={section} rows={data?.rows.filter(row => row.section === section) ?? []} totals={totals(section)} period={period} ledgerLink={ledgerLink} columns={columns} />)}
    {kind === "BALANCE_SHEET" && sections.includes("LIABILITIES") && <tr className="border-t-2 bg-slate-100 font-bold"><td className="px-2 py-2">Liabilitas + Ekuitas</td>{columns.map(metric => {
      const l = totals("LIABILITIES")?.[metric], e = totals("EQUITY")?.[metric];
      return <td key={metric} className="px-2 py-2 text-right tabular-nums">{money(l == null || e == null ? null : Number(l) + Number(e))}</td>;
    })}</tr>}
    {kind === "PROFIT_LOSS" && <tr className="border-t-2 bg-slate-100 font-bold"><td className="px-2 py-2">Laba / Rugi</td>{profit.map((value, index) => <td key={metrics[index]} className={`px-2 py-2 text-right tabular-nums ${value != null && value < 0 ? "text-red-600" : ""}`}>{money(value)}</td>)}</tr>}
  </tbody></table></div>;
  return <div className="print-document space-y-2">
    <PageHeader title={title} description={`${filters.as_of_date} · ${period} · ${scopeNames.join(" · ") || "Consolidated"}${filters.kap ? " · KAP" : ""}`} actions={<div className="flex gap-1 print:hidden">
      <Button variant="outline" size="sm" title="Filters" aria-label="Report filters" aria-expanded={showFilters} onClick={() => setShowFilters(!showFilters)}><ListFilter size={15} /></Button>
      {canManage && <Link to="/finance-setup/reports" className="inline-flex h-8 items-center rounded border px-2" title="Report setup" aria-label="Report setup"><Settings2 size={15} /></Link>}
      <Button variant="outline" size="sm" title="Export Excel" aria-label="Export Excel" disabled={!data} onClick={exportReport}><Download size={15} /></Button>
      {kind === "BALANCE_SHEET" ? (["KAP", "DETAIL"] as const).map(layout => <PrintPreviewButton key={layout} src={`/balance-sheet/print?${new URLSearchParams(Object.fromEntries(Object.entries({...params, kap:layout === "KAP", detail:layout === "DETAIL"}).map(([key,value])=>[key,String(value)])))}`} title={`Balance Sheet — ${layout}`} ariaLabel={`Print ${layout} balance sheet`} />) : <PrintPreviewButton src={`/profit-loss/print?${new URLSearchParams(Object.fromEntries(Object.entries(params).map(([key,value])=>[key,String(value)])))}`} title={title} ariaLabel="Print profit and loss" />}
      <Button variant="outline" size="sm" title="Refresh" aria-label="Refresh report" disabled={report.isFetching} onClick={() => report.refetch()}><RefreshCw size={15} /></Button>
    </div>} />
    {showFilters && <Card className="p-2 print:hidden"><form className="flex flex-wrap items-end gap-2" onSubmit={event => { event.preventDefault(); setFilters({ ...draft }); setShowFilters(false); }}>
      <label className="grid text-xs">As of<input className={input} type="date" required value={draft.as_of_date} onChange={event => setDraft({ ...draft, as_of_date: event.target.value })} /></label>
      <label className="grid text-xs">Unit<select className={input} value={draft.business_unit_id} onChange={event => setDraft({ ...draft, business_unit_id: event.target.value, location_id: "", department_id: "" })}><option value="">All units</option>{units.data?.map(unit => <option key={unit.id} value={unit.id}>{unit.name}</option>)}</select></label>
      <label className="grid text-xs">Location<select className={input} value={draft.location_id} onChange={event => setDraft({ ...draft, location_id: event.target.value })}><option value="">{locations.data?.length === 1 ? locations.data[0].name : "Consolidated"}</option>{locations.data?.map(location => <option key={location.id} value={location.id}>{location.name}</option>)}</select></label>
      <label className="grid text-xs">Department<select className={input} value={draft.department_id} onChange={event => setDraft({ ...draft, department_id: event.target.value })}><option value="">All departments</option>{departments.data?.map(department => <option key={department.id} value={department.id}>{department.name}</option>)}</select></label>
      <label className="grid text-xs">Budget<select className={input} value={draft.budget_id} onChange={event => setDraft({ ...draft, budget_id: event.target.value })}><option value="">Approved budgets</option>{budgets.data?.items?.filter((budget: { status: string }) => ["APPROVED", "LOCKED"].includes(budget.status)).map((budget: { id: number; name: string }) => <option key={budget.id} value={budget.id}>{budget.name}</option>)}</select></label>
      <label className="flex h-8 items-center gap-1 text-xs"><input type="checkbox" checked={draft.kap} onChange={event => setDraft({ ...draft, kap: event.target.checked })} />KAP headers</label>
      <label className="flex h-8 items-center gap-1 text-xs"><input type="checkbox" checked={draft.include_zero} onChange={event => setDraft({ ...draft, include_zero: event.target.checked })} />Zero values</label>
      <Button size="sm" type="submit">Apply</Button>
    </form></Card>}
    <div className="flex items-center gap-1 print:hidden">{(["MTD", "YTD"] as const).map(value => <Button key={value} size="sm" variant={period === value ? "primary" : "outline"} onClick={() => setPeriod(value)}>{value}</Button>)}</div>
    {report.isLoading ? <div className="p-4 text-sm">Loading report…</div> : report.isError ? <div role="alert" className="rounded border border-red-200 p-3 text-sm text-red-700">{error?.response?.data?.detail || "Report could not be loaded"}</div> : data && <>
      <div className="flex flex-wrap divide-x rounded border bg-white text-xs">{(kind === "PROFIT_LOSS" ? ["REVENUE", "COST_OF_REVENUE", "EXPENSES"] : ["ASSETS", "LIABILITIES", "EQUITY"]).map(section => <div key={section} className="px-3 py-2"><span className="mr-2 text-slate-500">{labels[section]}</span><b className="tabular-nums">{money(totals(section)?.current)}</b></div>)}{kind === "PROFIT_LOSS" && <div className="px-3 py-2"><span className="mr-2 text-slate-500">Laba / Rugi</span><b className="tabular-nums">{money(profit[0])}</b></div>}</div>
      {kind === "BALANCE_SHEET" ? <div className="grid items-start gap-2 xl:grid-cols-2">{table(["ASSETS"])}{table(["LIABILITIES", "EQUITY"])}</div> : table(["REVENUE", "COST_OF_REVENUE", "EXPENSES"])}
      {kind === "PROFIT_LOSS" && data.departments && <DepartmentPerformanceTable departments={data.departments} period={period} asOf={filters.as_of_date} locationId={data.scope.location_id} businessUnitId={data.scope.business_unit_id} />}
      <div className="hidden print:block text-xs">{user?.full_name || user?.username} · {new Date().toLocaleString()}</div>
    </>}
  </div>;
}

function ReportSection({ section, rows, totals, period, ledgerLink, columns }: { section: string; rows: Row[]; totals?: Amounts; period: Period; ledgerLink: (row: Row) => string; columns: (keyof Amounts)[] }) {
  return <><tr className="border-y bg-slate-50 font-semibold"><td className="px-2 py-1.5">{labels[section]}</td>{columns.map(metric => <td key={metric} className="px-2 py-1.5 text-right tabular-nums">{money(totals?.[metric])}</td>)}</tr>
    {rows.map(row => <tr key={`${row.account_code}-${row.account_name}`} className="border-b hover:bg-blue-50/40"><td className="max-w-[22rem] truncate px-2 py-1" title={row.account_name}>{row.account_code || !row.account_ids.length ? <Link className="text-blue-700 hover:underline" to={ledgerLink(row)}>{row.account_name}</Link> : <span>{row.account_name}</span>}</td>{columns.map(metric => <td key={metric} className={`px-2 py-1 text-right tabular-nums ${Number(row.periods[period][metric]) < 0 ? "text-red-600" : ""}`}>{money(row.periods[period][metric])}</td>)}</tr>)}</>;
}
