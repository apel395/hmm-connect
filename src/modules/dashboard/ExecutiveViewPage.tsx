import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ListFilter, RefreshCw } from "lucide-react";
import api from "@/api/client";
import useAuthStore from "@/store/auth";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/common/PageHeader";
import ForbiddenPage from "@/pages/errors/ForbiddenPage";
import { listBusinessUnits, listLocations } from "@/modules/admin/organization/api";
import { loadReportPreferences, saveReportPreferences } from "@/modules/finance/financial-statements/reportState";
import type { Amounts, Period, Report } from "@/modules/finance/financial-statements/FinancialReportPage";

const money = (value: string | number | null | undefined) => value == null ? "—" : Number(value).toLocaleString("id-ID", {maximumFractionDigits:0});
const field = "h-8 rounded border bg-white px-2 text-xs";

type HeadlineReport = Pick<Report,"presentation_rows" | "section_totals">;
type ExecutiveOverview = {scope:Report["scope"];scope_labels:NonNullable<Report["scope_labels"]>;profit_loss:HeadlineReport;balance_sheet:HeadlineReport};

export function ExecutiveSummary({ pnl, balance, period, asOf }: { pnl: HeadlineReport; balance: HeadlineReport; period: Period; asOf: string }) {
  const amounts = (key: string) => pnl.presentation_rows?.find(row => row.key === key)?.periods[period];
  const earnings = amounts("NOP")?.current, revenue = amounts("REVENUE")?.current;
  const margin = revenue != null && Number(revenue) !== 0 && earnings != null ? Number(earnings)/Number(revenue)*100 : null;
  const headlines = [["REVENUE","Revenue"],["BEBAN","Total expenses"],["GOP","Operating profit / loss"],["NOP","Net profit / loss"]] as const;
  return <>
    <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-4">{headlines.map(([key,label]) => <Card key={key} className="h-full p-3 "><div className="text-xs text-slate-500">{label}</div><div className={`mt-1 text-xl font-semibold tabular-nums ${Number(amounts(key)?.current) < 0 ? "text-red-700" : ""}`}>{money(amounts(key)?.current)}</div><div className="mt-1 text-xs text-slate-500">Budget {money(amounts(key)?.budget)}</div></Card>)}</div>
    <div className="grid gap-2 sm:grid-cols-4">{["ASSETS","LIABILITIES","EQUITY"].map(section => <Card key={section} className="h-full p-3 "><div className="text-xs text-slate-500">{{ASSETS:"Assets",LIABILITIES:"Liabilities",EQUITY:"Equity"}[section]} · {asOf}</div><div className="mt-1 text-lg font-semibold tabular-nums">{money(balance.section_totals[section]?.YTD.current)}</div></Card>)}<Card className="p-3"><div className="text-xs text-slate-500">Net profit margin</div><div className={`mt-1 text-lg font-semibold ${margin != null && margin < 0 ? "text-red-700" : ""}`}>{margin == null ? "—" : `${margin.toFixed(1)}%`}</div></Card></div>
    <Card className="overflow-x-auto p-3"><div className="mb-2 text-sm font-semibold">Performance overview · {period}</div><table className="w-full whitespace-nowrap text-xs"><thead><tr className="border-b"><th className="py-1 text-left">Measure</th>{["Current","Budget","Last month","Last year"].map(label => <th key={label} className="px-2 py-1 text-right">{label}</th>)}</tr></thead><tbody>{headlines.map(([key,label]) => <tr key={key} className="border-b"><td className="py-2">{label}</td>{(["current","budget","last_month","last_year"] as (keyof Amounts)[]).map(metric => <td key={metric} className="px-2 py-2 text-right tabular-nums">{money(amounts(key)?.[metric])}</td>)}</tr>)}</tbody></table></Card>
  </>;
}

export default function ExecutiveViewPage() {
  const user = useAuthStore(state => state.user);
  const canChooseBudget = useAuthStore(state=>state.hasPermission("finance.view"));
  const allowed = useAuthStore(state => state.hasPermission("reports.view") || state.hasPermission("finance.view"));
  const defaults = {as_of_date:new Date().toLocaleDateString("en-CA",{timeZone:"Asia/Jakarta"}),business_unit_id:"",location_id:"",department_id:"",budget_id:"",kap:false,include_zero:false,report_scope:"CONSOLIDATED"};
  const owner = String(user?.id ?? "anonymous");
  const [saved] = useState(() => loadReportPreferences(owner,"EXECUTIVE",window.location.search,defaults));
  const [filters,setFilters] = useState(saved.filters);
  const [draft,setDraft] = useState(saved.filters);
  const [period,setPeriod] = useState<Period>(saved.period);
  const [showFilters,setShowFilters] = useState(false);
  const units = useQuery({queryKey:["executive-units"],queryFn:listBusinessUnits,enabled:allowed});
  const locations = useQuery({queryKey:["executive-locations",draft.business_unit_id],queryFn:() => listLocations({is_active:true,business_unit_id:Number(draft.business_unit_id)||undefined}),enabled:allowed && showFilters});
  const budgets = useQuery({queryKey:["executive-budgets",draft.as_of_date.slice(0,4)],queryFn:async () => (await api.get<{items:{id:number;name:string;status:string}[]}>("/budgets",{params:{fiscal_year:draft.as_of_date.slice(0,4),page_size:500}})).data,enabled:allowed && canChooseBudget && showFilters});
  const params = {as_of_date:filters.as_of_date,business_unit_id:Number(filters.business_unit_id)||undefined,location_id:Number(filters.location_id)||undefined,department_id:Number(filters.department_id)||undefined,budget_id:Number(filters.budget_id)||undefined,detail:false};
  const overview = useQuery({queryKey:["executive-overview",params],queryFn:async () => (await api.get<ExecutiveOverview>("/financial-reports/executive",{params})).data,enabled:allowed});
  const persist = (next = filters, nextPeriod = period) => saveReportPreferences(owner,"EXECUTIVE",{filters:next,period:nextPeriod,view:"EXECUTIVE"});
  if (!allowed) return <ForbiddenPage/>;
  return <div className="space-y-2"><PageHeader title="Executive View" description={`${filters.as_of_date} · ${period} · ${overview.data?.scope_labels?.business_unit_id || "All units"} · ${overview.data?.scope_labels?.location_id || "Consolidated"} · ${overview.data?.scope.department_id != null ? `${overview.data.scope_labels?.department_id} · ` : ""}IDR`} actions={<div className="flex gap-1"><Button size="sm" variant="outline" title="Filters" aria-label="Executive view filters" onClick={() => setShowFilters(!showFilters)}><ListFilter size={15}/></Button><Button size="sm" variant="outline" title="Refresh" aria-label="Refresh executive view" onClick={() => {void overview.refetch();}}><RefreshCw size={15}/></Button></div>}/>
    {showFilters && <Card className="p-2"><form className="flex flex-wrap items-end gap-2" onSubmit={event => {event.preventDefault();setFilters(draft);persist(draft);setShowFilters(false);}}><label className="grid text-xs">As of<input type="date" required className={field} value={draft.as_of_date} onChange={event => setDraft({...draft,as_of_date:event.target.value})}/></label><label className="grid text-xs">Unit<select className={field} value={draft.business_unit_id} onChange={event => setDraft({...draft,business_unit_id:event.target.value,location_id:"",department_id:""})}><option value="">All units</option>{units.data?.map(unit => <option key={unit.id} value={unit.id}>{unit.name}</option>)}</select></label><label className="grid text-xs">Location<select className={field} value={draft.location_id} onChange={event => setDraft({...draft,location_id:event.target.value,department_id:""})}><option value="">Consolidated</option>{locations.data?.map(location => <option key={location.id} value={location.id}>{location.name}</option>)}</select></label>{canChooseBudget&&<label className="grid text-xs">Budget<select className={field} value={draft.budget_id} onChange={event => setDraft({...draft,budget_id:event.target.value})}><option value="">Approved budgets</option>{budgets.data?.items.filter(budget => ["APPROVED","LOCKED"].includes(budget.status)).map(budget => <option key={budget.id} value={budget.id}>{budget.name}</option>)}</select></label>}<Button size="sm" type="submit">Apply</Button></form></Card>}
    <div className="flex gap-1">{(["MTD","YTD"] as const).map(value => <Button key={value} size="sm" variant={period===value?"primary":"outline"} onClick={() => {setPeriod(value);persist(filters,value);}}>{value}</Button>)}</div>
    {overview.isPending ? <p className="p-3 text-sm">Loading executive overview…</p> : overview.isError ? <p role="alert" className="p-3 text-sm text-red-700">Executive overview could not load. Refresh to retry.</p> : <ExecutiveSummary pnl={overview.data.profit_loss} balance={overview.data.balance_sheet} period={period} asOf={filters.as_of_date}/>}
  </div>;
}
