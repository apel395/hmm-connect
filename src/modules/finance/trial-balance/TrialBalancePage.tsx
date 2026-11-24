import { ExportButton } from "@/components/common/ReportActions";
import { GENERIC_REPORT_PRINT_NOTE } from "@/components/common/reportActionCopy";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { useEffect, useState } from "react";
import { SlidersHorizontal } from "lucide-react";
import { todayLocal } from "@/utils/dateConstraints";
import { toast } from "sonner";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import { exportTrialBalanceXlsx, getTrialBalance, TrialBalanceFilters } from "./api";
import { listBusinessUnits, listLocations } from "@/modules/admin/organization/api";
import SearchableSelect from "@/components/form/SearchableSelect";

const today = todayLocal();
const yearStart = `${today.slice(0, 4)}-01-01`;
const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = "h-7 rounded border border-slate-300 bg-white px-2 text-xs";

export default function TrialBalancePage() {
  const [draft, setDraft] = useState<TrialBalanceFilters>({ date_from: yearStart, date_to: today, page: 1, page_size: 50, search: "", include_zero_balance: false });
  const [filters, setFilters] = useState<TrialBalanceFilters>(draft);
  const [showFilters, setShowFilters] = useState(false);
  const [exporting, setExporting] = useState(false);
  const availableYears = Array.from({ length: Math.max(1, Number(today.slice(0, 4)) - 2025) }, (_, i) => 2026 + i);
  const locations = useQuery({
    queryKey: ["trial-balance-locations", draft.business_unit_id],
    queryFn: () => listLocations({ is_active: true, business_unit_id: draft.business_unit_id }),
  });
  const businessUnits = useQuery({ queryKey: ["report-units"], queryFn: listBusinessUnits });
  useEffect(() => {
    if (locations.data?.length === 1 && !draft.location_id) {
      const location_id = locations.data[0].id;
      setDraft((current) => ({ ...current, location_id }));
      setFilters((current) => ({ ...current, location_id, page: 1 }));
    }
  }, [locations.data, draft.location_id]);
  useEffect(() => {
    if (businessUnits.data?.length === 1 && !filters.business_unit_id) {
      const business_unit_id = businessUnits.data[0].id;
      setDraft((current) => ({ ...current, business_unit_id }));
      setFilters((current) => ({ ...current, business_unit_id, location_id: undefined, page: 1 }));
    }
  }, [businessUnits.data, filters.business_unit_id]);
  const query = useQuery({ queryKey: ["trial-balance", filters], queryFn: () => getTrialBalance(filters) });
  const data = query.data;
  const summary = data?.summary as Record<string, string | number | boolean> | undefined;
  const printParams = Object.fromEntries(Object.entries(filters).filter(([key, value]) => key !== "page" && key !== "page_size" && value !== "" && value !== undefined));
  const printQuery = new URLSearchParams(Object.fromEntries(Object.entries(printParams).map(([key, value]) => [key, String(value)]))).toString();
  const printSrc = `/journal/trial-balance/print${printQuery ? `?${printQuery}` : ""}`;

  const changeFilters = (patch: Partial<TrialBalanceFilters>) => {
    setDraft(current => ({ ...current, ...patch, page: 1 }));
    setFilters(current => ({ ...current, ...patch, page: 1 }));
  };
  const downloadExcel = async () => {
    setExporting(true);
    try {
      await exportTrialBalanceXlsx(filters);
    } catch {
      toast.error("Trial Balance Excel export failed.");
    } finally {
      setExporting(false);
    }
  };

  const activeChips = [
    filters.date_from && `From: ${filters.date_from}`,
    filters.date_to && `To: ${filters.date_to}`,
    filters.search && `Search: ${filters.search}`,
    filters.business_unit_id && `Unit: ${businessUnits.data?.find(unit => unit.id === filters.business_unit_id)?.name ?? filters.business_unit_id}`,
    filters.location_id && `Location: ${locations.data?.find(row => row.id === filters.location_id)?.name ?? filters.location_id}`,
    filters.department_id && `Department: ${filters.department_id}`,
    filters.include_zero_balance && "Include zero balances",
  ].filter(Boolean) as string[];
  const clearFilters = () => {
    const reset: TrialBalanceFilters = { date_from: yearStart, date_to: today, page: 1, page_size: filters.page_size ?? 50, search: "", include_zero_balance: false };
    setDraft(reset); setFilters(reset);
  };

  return <DataWorkspace area="Accounting" className="data-first">
    <div className="df-toolbar print:hidden" aria-label="Trial balance toolbar">
      <label className="flex items-center gap-1 text-[11px] text-slate-600">From<input aria-label="From date" type="date" className="df-field" value={filters.date_from} onChange={e => changeFilters({ date_from: e.target.value })} /></label>
      <label className="flex items-center gap-1 text-[11px] text-slate-600">To<input aria-label="To date" type="date" className="df-field" value={filters.date_to} onChange={e => changeFilters({ date_to: e.target.value })} /></label>
      <input className="df-search" aria-label="Search accounts" placeholder="Account code or name" value={filters.search || ""} onChange={e => changeFilters({ search: e.target.value })} />
      <select aria-label="Report business unit" className="df-field" value={filters.business_unit_id ?? ""} onChange={e => changeFilters({ business_unit_id: Number(e.target.value) || undefined, location_id: undefined, department_id: undefined })}>
        <option value="">Consolidated</option>
        {businessUnits.data?.map(unit => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
      </select>
      <Button type="button" size="sm" variant="outline" aria-expanded={showFilters} onClick={() => setShowFilters(value => !value)}><SlidersHorizontal size={14}/> Filters</Button>
      <div className="ml-auto flex items-center gap-1">
        <ExportButton scope="filtered" format="excel" disabled={!data} loading={exporting} onClick={downloadExcel} />
        <PrintPreviewButton src={printSrc} title="Trial Balance" ariaLabel="Preview trial balance" label="Print" note={GENERIC_REPORT_PRINT_NOTE} />
      </div>
    </div>
    {activeChips.length > 0 && <div className="df-chips print:hidden" aria-label="Active filters">{activeChips.map(chip => <span key={chip} className="df-chip">{chip}</span>)}<button type="button" className="text-[11px] font-medium text-emerald-800 hover:underline" onClick={clearFilters}>Clear all</button></div>}
    {showFilters && <Card className="df-filters print:hidden p-2">
      <form className="grid gap-2 md:grid-cols-6" onSubmit={(event) => { event.preventDefault(); setFilters({ ...draft, page: 1 }); setShowFilters(false); }}>
        <label className="text-xs">Fiscal year<select className={`${input} mt-1 w-full`} value={draft.date_from.slice(0, 4)} onChange={(e) => {
          const year = e.target.value;
          setDraft({ ...draft, date_from: `${year}-01-01`, date_to: year === today.slice(0, 4) ? today : `${year}-12-31` });
        }}>{availableYears.map(year => <option key={year} value={year}>{year}</option>)}</select></label>
        <label className="text-xs">From date<input className={`${input} mt-1 w-full`} type="date" required min={`${draft.date_from.slice(0,4)}-01-01`} max={draft.date_to} value={draft.date_from} onChange={e => setDraft({ ...draft, date_from: e.target.value })}/></label>
        <label className="text-xs">To date<input className={`${input} mt-1 w-full`} type="date" min={draft.date_from} max={`${draft.date_from.slice(0, 4)}-12-31`} value={draft.date_to} onChange={e => setDraft({ ...draft, date_to: e.target.value })}/></label>
        <label className="text-xs">Search<input className={`${input} mt-1 w-full`} placeholder="Account code or name" value={draft.search || ""} onChange={(e) => setDraft({ ...draft, search: e.target.value })}/></label>
        <label className="text-xs">Location<SearchableSelect value={draft.location_id} disabled={(locations.data?.length ?? 0) <= 1} placeholder="Type location code or name..." options={(locations.data??[]).map((row:any)=>({id:row.id,label:`${row.code} — ${row.name}`,keywords:[row.code??"",row.name??""]}))} onChange={(id)=>setDraft({...draft,location_id:id})}/></label>
        <div className="flex items-end gap-2"><Button type="submit">Apply</Button><label className="flex items-center gap-2 pb-1 text-[11px]"><input type="checkbox" checked={Boolean(draft.include_zero_balance)} onChange={(e) => setDraft({ ...draft, include_zero_balance: e.target.checked })}/>Include zero balance</label></div>
      </form>
    </Card>}
    <Card className="workspace-data p-0">
      {query.isLoading ? <div className="p-10 text-center text-sm text-slate-500">Loading trial balance…</div> : query.isError ? <div className="p-10 text-center text-sm text-red-600">Trial balance could not be loaded.</div> : <Table variant="grid" stickyHeader containerClassName="overflow-auto border-0 shadow-none print:max-h-none print:overflow-visible"><THead><TR><TH>Account</TH><TH className="text-right">Opening Balance</TH>{filters.date_from.slice(5) !== "01-01" && <><TH className="text-right">Prior Debit</TH><TH className="text-right">Prior Credit</TH></>}<TH className="text-right">Debit Movement</TH><TH className="text-right">Credit Movement</TH><TH className="text-right">Closing</TH><TH>Status</TH></TR></THead><TBody>{data?.items.map((row)=>{const glParams=new URLSearchParams({account_id:String(row.account_id),date_from:filters.date_from,date_to:filters.date_to,...(filters.location_id?{location_id:String(filters.location_id)}:{}),...(filters.business_unit_id?{business_unit_id:String(filters.business_unit_id)}:{})}).toString();return <TR key={row.account_id}><TD className="font-medium"><Link className="text-emerald-700 hover:underline" to={`/general-ledger?${glParams}`}>{row.account_code} · {row.account_name}</Link></TD><TD className={`text-right ${Number(row.opening_balance) < 0 ? "text-rose-700" : ""}`}>{money(row.opening_balance)}</TD>{filters.date_from.slice(5) !== "01-01" && <><TD className="text-right">{money(row.prior_debit)}</TD><TD className="text-right">{money(row.prior_credit)}</TD></>}<TD className="text-right">{money(row.period_debit)}</TD><TD className="text-right">{money(row.period_credit)}</TD><TD className={`text-right font-medium ${Number(row.closing_balance) < 0 ? "text-rose-700" : ""}`}>{money(row.closing_balance)}</TD><TD><span className={`inline-flex rounded-full px-2 py-0.5 text-xs font-semibold ring-1 ring-inset ${row.status === "ABNORMAL" ? "bg-rose-50 text-rose-700 ring-rose-200" : "bg-emerald-50 text-emerald-700 ring-emerald-200"}`}>{row.status === "ABNORMAL" ? "Abnormal" : "Normal"}</span></TD></TR>})}</TBody></Table>}
    </Card>
    <div className="df-statusbar print:hidden" aria-label="Trial balance status">
      <span><strong>{data?.total_items ?? 0}</strong> accounts</span>
      <span>Debit <strong>{summary?.period_debit != null ? money(summary.period_debit) : "—"}</strong></span>
      <span>Credit <strong>{summary?.period_credit != null ? money(summary.period_credit) : "—"}</strong></span>
      <span className={summary?.is_balanced === false ? "text-red-700" : ""}>Diff <strong>{summary?.difference != null ? money(summary.difference) : "—"}</strong></span>
      <span className={summary?.is_balanced === false ? "text-red-700" : "text-emerald-700"}>{summary?.is_balanced === undefined ? "—" : summary.is_balanced ? "Balanced" : "Out of balance"}</span>
      <span className="df-spacer" />
      <label>Rows <select className="ml-1 rounded border border-slate-300 bg-white px-1" value={filters.page_size ?? 50} onChange={e => {
        const page_size = Number(e.target.value);
        setDraft(current => ({ ...current, page_size }));
        setFilters(current => ({ ...current, page_size, page: 1 }));
      }}>{[50, 100, 200].map(size => <option key={size} value={size}>{size}</option>)}</select></label>
      <span>Page {filters.page ?? 1} / {Math.max(data?.total_pages ?? 0, 1)}</span>
      <Button size="sm" variant="outline" disabled={!data?.has_previous} onClick={() => setFilters({ ...filters, page: Math.max(1, Number(filters.page || 1) - 1) })}>‹</Button>
      <Button size="sm" variant="outline" disabled={!data?.has_next} onClick={() => setFilters({ ...filters, page: Number(filters.page || 1) + 1 })}>›</Button>
    </div>
  </DataWorkspace>;
}
