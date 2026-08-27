import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AlertTriangle, RefreshCw } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { FinanceDashboardFilters, getFinanceDashboard } from "./api";
import { listBusinessUnits, listLocations, listDepartments } from "@/modules/admin/organization/api";

const today = new Date().toISOString().slice(0, 10);
const monthStart = `${today.slice(0, 8)}01`;
const initial: FinanceDashboardFilters = { as_of_date: today, date_from: monthStart, date_to: today, business_unit_id: "", location_id: "", department_id: "", cash_account_id: "", currency: "IDR" };
const money = (value: unknown) => new Intl.NumberFormat("id-ID", { style: "currency", currency: "IDR", maximumFractionDigits: 0 }).format(Number(value || 0));
const input = "h-9 rounded-lg border border-slate-300 bg-white px-3 text-sm";

export default function FinanceDashboardPage() {
  const [draft, setDraft] = useState(initial);
  const [filters, setFilters] = useState(initial);
  const query = useQuery({ queryKey: ["finance-dashboard", filters], queryFn: () => getFinanceDashboard(filters) });
  const businessUnits = useQuery({ queryKey: ["business-units"], queryFn: listBusinessUnits });
  const locations = useQuery({ queryKey: ["organization-locations", draft.business_unit_id, "assigned"], queryFn: () => listLocations({ business_unit_id: draft.business_unit_id ? Number(draft.business_unit_id) : undefined, is_active: true, assigned_only: true }) });
  const departments = useQuery({ queryKey: ["organization-departments", draft.business_unit_id], queryFn: () => listDepartments(draft.business_unit_id ? Number(draft.business_unit_id) : undefined) });
  const data = query.data;
  const set = (key: keyof FinanceDashboardFilters, value: string) => setDraft((current) => ({ ...current, [key]: value }));

  return <div className="space-y-5">
    <PageHeader title="Finance Dashboard" description="Cash position, Accounts Payable, purchasing commitments, profitability, and finance exceptions." actions={<Button variant="outline" onClick={() => query.refetch()}><RefreshCw size={15}/> Refresh</Button>} />
    <Card><form className="grid gap-2 md:grid-cols-3 xl:grid-cols-7" onSubmit={(event) => { event.preventDefault(); setFilters({ ...draft }); }}>
      <label className="text-xs text-slate-600">From<input className={`${input} mt-1 w-full`} type="date" value={draft.date_from} onChange={(e) => set("date_from", e.target.value)}/></label>
      <label className="text-xs text-slate-600">To<input className={`${input} mt-1 w-full`} type="date" value={draft.date_to} onChange={(e) => set("date_to", e.target.value)}/></label>
      <label className="text-xs text-slate-600">As of<input className={`${input} mt-1 w-full`} type="date" value={draft.as_of_date} onChange={(e) => set("as_of_date", e.target.value)}/></label>
      <label className="text-xs text-slate-600">Business Unit<select className={`${input} mt-1 w-full`} value={draft.business_unit_id} onChange={(e) => setDraft({...draft,business_unit_id:e.target.value,location_id:"",department_id:""})}><option value="">All</option>{businessUnits.data?.map((x:any)=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></label>
      <label className="text-xs text-slate-600">Location<select className={`${input} mt-1 w-full`} value={draft.location_id} onChange={(e) => set("location_id", e.target.value)}><option value="">All</option>{locations.data?.map((x:any)=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></label>
      <label className="text-xs text-slate-600">Department<select className={`${input} mt-1 w-full`} value={draft.department_id} onChange={(e) => set("department_id", e.target.value)}><option value="">All</option>{departments.data?.map((x:any)=><option key={x.id} value={x.id}>{x.code} — {x.name}</option>)}</select></label>
      <div className="flex items-end gap-2"><Button type="submit">Apply</Button><Button type="button" variant="outline" onClick={() => { setDraft(initial); setFilters(initial); }}>Reset</Button></div>
    </form></Card>
    {query.isLoading && <Card className="p-10 text-center text-slate-500">Loading finance dashboard…</Card>}
    {query.isError && <Card className="border-red-200 bg-red-50 p-4 text-red-700">Finance dashboard could not be loaded.</Card>}
    {data && <>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <Metric label="Current Cash" value={data.cash_position?.total_liquid_cash}/><Metric label="Outstanding AP" value={data.accounts_payable?.total_outstanding_ap}/><Metric label="Overdue AP" value={data.accounts_payable?.overdue_ap} warning/><Metric label="Payments Due Today" value={data.accounts_payable?.due_today}/><Metric label="Net Cash Flow" value={data.cash_flow?.net_cash_flow}/><Metric label="Net Profit" value={data.profitability?.net_profit_after_tax}/>
      </div>
      <Card className="p-4"><div className="mb-3 flex items-center justify-between"><div><h2 className="font-semibold">Cash Forecast</h2><p className="text-xs text-slate-500">Projected cash after known Accounts Payable and approved purchasing commitments.</p></div><Link className="text-sm text-emerald-700" to="/accounts-payable">Open AP</Link></div><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><Forecast label="Due Today" value={data.accounts_payable?.due_today}/><Forecast label="Due Next 7 Days" value={data.accounts_payable?.due_next_7_days}/><Forecast label="Due Next 30 Days" value={data.accounts_payable?.due_next_30_days}/><Forecast label="After All AP" value={data.forecast?.forecast_after_all_outstanding_ap}/><Forecast label="After AP + Approved PO" value={data.forecast?.forecast_after_ap_and_po_commitments}/></div></Card>
      <div className="grid gap-4 xl:grid-cols-2"><Card className="p-4"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Cash Movement</h2><Link className="text-sm text-emerald-700" to="/cash-flow">Open Cash Flow</Link></div><div className="grid grid-cols-3 gap-3"><Forecast label="Opening" value={data.cash_flow?.opening_cash}/><Forecast label="Inflow" value={data.cash_flow?.total_inflow}/><Forecast label="Outflow" value={data.cash_flow?.total_outflow}/></div></Card><Card className="p-4"><div className="mb-3 flex items-center justify-between"><h2 className="font-semibold">Purchasing Commitments</h2><Link className="text-sm text-emerald-700" to="/purchase-orders">Open Purchasing</Link></div><div className="grid grid-cols-2 gap-3"><Forecast label="Approved PO Commitments" value={data.forecast?.approved_po_commitments}/><Forecast label="Planned PR Value" value={data.forecast?.planned_pr_value}/></div></Card></div>
      {data.alerts?.length>0&&<Card className="p-4"><h2 className="mb-3 font-semibold">Finance Exceptions</h2><div className="grid gap-2 md:grid-cols-2">{data.alerts.map((alert:any,index:number)=><Link key={`${alert.alert_type}-${index}`} to={alert.target_route||"/finance-dashboard"} className="flex gap-3 rounded-lg border p-3 hover:bg-slate-50"><AlertTriangle size={18} className={alert.severity==="CRITICAL"?"text-red-600":"text-amber-600"}/><div className="min-w-0 flex-1"><div className="flex justify-between gap-2"><span className="font-medium">{alert.title}</span><Badge variant={alert.severity==="CRITICAL"?"danger":"warning"}>{alert.count??1}</Badge></div><div className="text-xs text-slate-500">{alert.description}{alert.amount!=null?` · ${money(alert.amount)}`:""}</div></div></Link>)}</div></Card>}
      {data.bank_reconciliation&&<Link to="/bank-reconciliations"><Card className="grid gap-3 p-4 sm:grid-cols-3"><Forecast label="Pending Reconciliations" value={data.bank_reconciliation.pending_count} plain/><Forecast label="Oldest Statement" value={data.bank_reconciliation.oldest_unreconciled_statement_date||"—"} plain/><Forecast label="Reconciliation Difference" value={data.bank_reconciliation.total_difference}/></Card></Link>}
    </>}
  </div>;
}

function Metric({label,value,warning=false}:{label:string;value:unknown;warning?:boolean}){return <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">{label}</div><div className={`mt-2 text-xl font-semibold ${warning?"text-amber-700":""}`}>{money(value)}</div></Card>}
function Forecast({label,value,plain=false}:{label:string;value:unknown;plain?:boolean}){return <div className="rounded border bg-slate-50 p-3"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 font-semibold">{plain?String(value??"—"):money(value)}</div></div>}
