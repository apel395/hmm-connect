import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ListFilter, RefreshCw, TrendingUp, Wallet, Landmark, CircleDollarSign } from "lucide-react";
import { ResponsiveContainer, ComposedChart, Line, BarChart, Bar, CartesianGrid, XAxis, YAxis, Tooltip, Legend } from "recharts";
import api from "@/api/client";
import useAuthStore from "@/store/auth";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import PageHeader from "@/components/common/PageHeader";
import ForbiddenPage from "@/pages/errors/ForbiddenPage";
import ReportUnitButtons from "@/components/reports/ReportUnitButtons";
import { listLocations } from "@/modules/admin/organization/api";
import { loadReportPreferences, saveReportPreferences } from "@/modules/finance/financial-statements/reportState";
import type { Period, Report } from "@/modules/finance/financial-statements/FinancialReportPage";

const money=(v:string|number|null|undefined)=>v==null?"—":Number(v).toLocaleString("id-ID",{maximumFractionDigits:0});
const compact=(v:number)=>Math.abs(v)>=1e9?`${(v/1e9).toFixed(1)}B`:Math.abs(v)>=1e6?`${(v/1e6).toFixed(1)}M`:Math.abs(v)>=1e3?`${(v/1e3).toFixed(0)}K`:String(v);
const field="h-8 rounded border bg-white px-2 text-xs";
type Headlines=Pick<Report,"presentation_rows"|"section_totals">;
type Performance={name:string;unit:string;dimension:string;MTD:{revenue:string;expenses:string;net_profit:string};YTD:{revenue:string;expenses:string;net_profit:string}};
type Overview={scope:Report["scope"];scope_labels:NonNullable<Report["scope_labels"]>;profit_loss:Headlines;balance_sheet:Headlines;dashboard:{monthly:{month:string;revenue:string;expenses:string;net_profit:string}[];performance:Performance[];expense_breakdown:Record<Period,{name:string;amount:string}[]>;cash_balance:string|null;activity_count:number}};

export function ExecutiveSummary({pnl,balance,period,asOf,cash}:{pnl:Headlines;balance:Headlines;period:Period;asOf:string;cash?:string|null}) {
  const amount=(key:string)=>pnl.presentation_rows?.find(row=>row.key===key)?.periods[period];
  const revenue=amount("REVENUE")?.current,profit=amount("NOP")?.current;
  const margin=revenue!=null&&Number(revenue)!==0&&profit!=null?Number(profit)/Number(revenue)*100:null;
  return <>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">{([['REVENUE','Revenue',TrendingUp],['BEBAN','Expenses',CircleDollarSign],['GOP','Operating profit',Landmark],['NOP','Net profit',Wallet]] as const).map(([key,label,Icon])=><Card key={key} className="relative overflow-hidden border-slate-200 p-4"><Icon className="absolute right-3 top-3 h-5 w-5 text-emerald-600"/><div className="text-xs font-medium text-slate-500">{label} · {period}</div><div className={`mt-2 text-2xl font-semibold tabular-nums ${Number(amount(key)?.current)<0?'text-rose-700':'text-slate-900'}`}>{money(amount(key)?.current)}</div><div className="mt-3 flex flex-wrap gap-x-3 gap-y-1 text-[11px] text-slate-500"><span>Budget {money(amount(key)?.budget)}</span><span>Last year {money(amount(key)?.last_year)}</span></div></Card>)}</div>
    <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">{(['ASSETS','LIABILITIES','EQUITY'] as const).map(section=><Card key={section} className="p-3"><div className="text-xs text-slate-500">{{ASSETS:'Assets',LIABILITIES:'Liabilities',EQUITY:'Equity'}[section]}</div><div className="mt-1 text-lg font-semibold tabular-nums">{money(balance.section_totals[section]?.YTD.current)}</div><div className="mt-1 text-[10px] text-slate-400">{asOf}</div></Card>)}<Card className="p-3"><div className="text-xs text-slate-500">Cash & bank</div><div className="mt-1 text-lg font-semibold">{money(cash)}</div></Card><Card className="p-3"><div className="text-xs text-slate-500">Net profit margin</div><div className={`mt-1 text-lg font-semibold ${margin!=null&&margin<0?'text-rose-700':'text-emerald-700'}`}>{margin==null?'—':`${margin.toFixed(1)}%`}</div></Card></div>
  </>;
}

function DashboardCharts({data,period}:{data:Overview;period:Period}) {
  const monthly=data.dashboard.monthly.map(row=>({...row,label:row.month.slice(5),revenue:Number(row.revenue),net_profit:Number(row.net_profit)}));
  const expenses=data.dashboard.expense_breakdown[period].filter(row=>Number(row.amount)!==0).map(row=>({name:row.name,amount:Number(row.amount)}));
  const performance=data.dashboard.performance.map(row=>({name:`${row.unit} · ${row.name}`,profit:Number(row[period].net_profit)})).sort((a,b)=>Math.abs(b.profit)-Math.abs(a.profit)).slice(0,10);
  return <div className="grid gap-3 xl:grid-cols-3">
    <Card className="p-4 xl:col-span-2"><h2 className="text-sm font-semibold">Revenue & profit trend</h2><p className="mt-1 text-xs text-slate-500">{monthly[0]?.month.slice(0,4)} · IDR · monthly activity</p><div className="mt-3 h-72"><ResponsiveContainer width="100%" height="100%"><ComposedChart data={monthly}><CartesianGrid strokeDasharray="3 3" vertical={false}/><XAxis dataKey="label" tick={{fontSize:11}}/><YAxis tickFormatter={compact} tick={{fontSize:11}}/><Tooltip formatter={value=>money(Number(value))}/><Legend/><Line dataKey="revenue" name="Revenue" stroke="#059669" strokeWidth={3}/><Line dataKey="net_profit" name="Net profit" stroke="#2563eb" strokeWidth={3}/></ComposedChart></ResponsiveContainer></div></Card>
    <Card className="p-4"><h2 className="text-sm font-semibold">Expense breakdown · {period}</h2>{expenses.length?<div className="mt-3 h-72"><ResponsiveContainer width="100%" height="100%"><BarChart data={expenses} layout="vertical"><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" tickFormatter={compact} tick={{fontSize:10}}/><YAxis type="category" dataKey="name" width={115} tick={{fontSize:10}}/><Tooltip formatter={value=>money(Number(value))}/><Bar dataKey="amount" name="Expenses" fill="#d97706" radius={[0,4,4,0]}/></BarChart></ResponsiveContainer></div>:<div className="flex h-72 items-center justify-center text-sm text-slate-500">No posted expenses in this period.</div>}</Card>
    <Card className="p-4 xl:col-span-3"><h2 className="text-sm font-semibold">Performance by department / location · {period}</h2>{performance.length?<div className="mt-3" style={{height:Math.max(240,performance.length*36)}}><ResponsiveContainer width="100%" height="100%"><BarChart data={performance} layout="vertical"><CartesianGrid strokeDasharray="3 3" horizontal={false}/><XAxis type="number" tickFormatter={compact} tick={{fontSize:11}}/><YAxis type="category" dataKey="name" width={190} tick={{fontSize:11}}/><Tooltip formatter={value=>money(Number(value))}/><Bar dataKey="profit" name="Net profit" fill="#0f766e" radius={[0,4,4,0]}/></BarChart></ResponsiveContainer></div>:<div className="p-8 text-center text-sm text-slate-500">No posted activity for the selected scope.</div>}</Card>
  </div>;
}

export default function ExecutiveViewPage() {
  const user=useAuthStore(state=>state.user);
  const allowed=useAuthStore(state=>state.hasPermission('reports.view')||state.hasPermission('finance.view'));
  const owner=String(user?.id??'anonymous');
  const defaults={as_of_date:new Date().toLocaleDateString('en-CA',{timeZone:'Asia/Jakarta'}),business_unit_id:'',location_id:'',department_id:'',budget_id:'',kap:false,include_zero:false,report_scope:'CONSOLIDATED'};
  const [saved]=useState(()=>loadReportPreferences(owner,'EXECUTIVE',window.location.search,defaults));
  const [filters,setFilters]=useState(saved.filters);
  const [draft,setDraft]=useState(saved.filters);
  const [period,setPeriod]=useState<Period>(saved.period);
  const [showFilters,setShowFilters]=useState(false);
  const locations=useQuery({queryKey:['executive-locations',draft.business_unit_id],queryFn:()=>listLocations({is_active:true,business_unit_id:Number(draft.business_unit_id)||undefined}),enabled:allowed&&showFilters});
  const params={as_of_date:filters.as_of_date,business_unit_id:Number(filters.business_unit_id)||undefined,location_id:Number(filters.location_id)||undefined,department_id:Number(filters.department_id)||undefined,budget_id:Number(filters.budget_id)||undefined};
  const report=useQuery({queryKey:['executive-overview',params],queryFn:async()=>(await api.get<Overview>('/financial-reports/executive',{params})).data,enabled:allowed});
  const persist=(next=filters,p=period)=>saveReportPreferences(owner,'EXECUTIVE',{filters:next,period:p,view:'EXECUTIVE'});
  if(!allowed)return <ForbiddenPage/>;
  return <div className="space-y-3"><PageHeader title="Executive View" description={`Owner dashboard · ${filters.as_of_date} · ${report.data?.scope_labels.business_unit_id||'Consolidated'} · IDR`} actions={<><Button size="sm" variant="outline" title="Filters" aria-label="Dashboard filters" onClick={()=>setShowFilters(!showFilters)}><ListFilter size={15}/></Button><Button size="sm" variant="outline" title="Refresh" aria-label="Refresh dashboard" onClick={()=>void report.refetch()}><RefreshCw size={15}/></Button></>}/>
    <div className="flex flex-wrap items-center justify-between gap-2"><ReportUnitButtons value={filters.business_unit_id} onChange={id=>{const next={...filters,business_unit_id:id,location_id:'',department_id:''};setFilters(next);setDraft(next);persist(next);}}/><div className="flex gap-1">{(['MTD','YTD'] as const).map(value=><Button key={value} size="sm" variant={period===value?'primary':'outline'} onClick={()=>{setPeriod(value);persist(filters,value);}}>{value}</Button>)}</div></div>
    {showFilters&&<Card className="p-3"><form className="flex flex-wrap items-end gap-2" onSubmit={event=>{event.preventDefault();setFilters(draft);persist(draft);setShowFilters(false);}}><label className="grid text-xs">As of<input type="date" required className={field} value={draft.as_of_date} onChange={event=>setDraft({...draft,as_of_date:event.target.value})}/></label><label className="grid text-xs">Location<select className={field} value={draft.location_id} onChange={event=>setDraft({...draft,location_id:event.target.value,department_id:''})}><option value="">All accessible locations</option>{locations.data?.map(location=><option key={location.id} value={location.id}>{location.name}</option>)}</select></label><Button size="sm" type="submit">Apply</Button></form></Card>}
    {report.isPending?<div className="p-8 text-sm text-slate-500">Loading owner dashboard…</div>:report.isError?<p role="alert" className="p-3 text-sm text-red-700">Dashboard could not load. Refresh to retry.</p>:<><ExecutiveSummary pnl={report.data.profit_loss} balance={report.data.balance_sheet} period={period} asOf={filters.as_of_date} cash={report.data.dashboard.cash_balance}/><DashboardCharts data={report.data} period={period}/></>}
  </div>;
}
