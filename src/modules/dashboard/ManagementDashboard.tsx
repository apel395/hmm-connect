import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Printer, RefreshCw } from "lucide-react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import api from "@/api/client";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import type { DepartmentPerformance } from "@/modules/finance/financial-statements/DepartmentPerformanceTable";
import DepartmentPerformanceTable from "@/modules/finance/financial-statements/DepartmentPerformanceTable";

type Performance = Record<"revenue" | "cogs" | "operating_expenses" | "other_expenses" | "goi" | "gop" | "nop", string> & { gop_margin: string | null; nop_margin: string | null };
type Ranking = { account_id: number; account_name: string; amount: string };
type Dashboard = { as_of_date: string; scope: { location_id: number | null }; scope_labels: Record<string, string>;
  MTD: Performance; YTD: Performance; monthly: (Performance & { month: number })[];
  departments: DepartmentPerformance[]; top_revenue: Ranking[]; top_cost: Ranking[];
  negative_assets: {account_name: string; account_ids: number[]; periods: {YTD: {current: string}}}[]; position: Record<string, string>; balance_gap: string; definitions: Record<string, string> };
const money = (v: string | number | null) => v == null ? "—" : Number(v).toLocaleString("id-ID", { maximumFractionDigits: 0 });
const rows = [["revenue", "Revenue"], ["cogs", "Cost of revenue"], ["goi", "Gross operating income"], ["operating_expenses", "Operating expenses"], ["gop", "Gross operating profit"], ["other_expenses", "Other / unclassified expenses"], ["nop", "Net operating profit"]] as const;
const monthName = (m: number) => new Intl.DateTimeFormat("en-GB", { month: "short" }).format(new Date(2026, m - 1, 1));

export default function ManagementDashboard() {
  const today = new Date().toLocaleDateString("en-CA", { timeZone: "Asia/Jakarta" });
  const [period, setPeriod] = useState(today.slice(0, 7));
  const [mode, setMode] = useState<"MTD" | "YTD">("MTD");
  const [year, month] = period.split("-").map(Number);
  const query = useQuery({ queryKey: ["management-dashboard", year, month], queryFn: async () => (await api.get<Dashboard>("/dashboard/management", { params: { year, month } })).data });
  const data = query.data;
  const scope = data?.scope.location_id ? `&location_id=${data.scope.location_id}` : "";
  const report = (kind: "profit-loss" | "balance-sheet") => `/${kind}?as_of_date=${data?.as_of_date}${scope}`;
  const ranking = (title: string, values: Ranking[]) => <Card className="p-3"><h3 className="mb-2 text-sm font-semibold">{title}</h3><table className="w-full text-xs"><tbody>{values.map(row => <tr key={row.account_id} className="border-b"><td className="py-1"><Link className="text-blue-700 hover:underline" to={`/general-ledger?account_id=${row.account_id}&date_from=${period}-01&date_to=${data?.as_of_date}${scope}`}>{row.account_name}</Link></td><td className="py-1 text-right tabular-nums">{money(row.amount)}</td></tr>)}</tbody></table>{!values.length && <p className="text-xs text-slate-500">No posted activity.</p>}</Card>;
  return <section className="management-dashboard space-y-3">
    <style>{`@media print { @page { size:A4 landscape; margin:10mm; } .management-dashboard { font:9pt Arial; } .management-dashboard table { width:100%; } .management-dashboard thead { display:table-header-group; } .management-dashboard tr { break-inside:avoid; } }`}</style>
    <header className="flex flex-wrap items-center justify-between gap-2 border-b pb-2"><div><h1 className="text-xl font-semibold">Financial Management Dashboard</h1><p className="text-xs text-slate-500">{data?.scope_labels.location_id || "Consolidated"} · {period} · IDR</p></div><div className="flex items-center gap-1 print:hidden">
      <input type="month" aria-label="Dashboard month" min="2026-01" value={period} onChange={e => { if (e.target.value) setPeriod(e.target.value); }} className="h-8 rounded border px-2 text-xs" />
      <select aria-label="Dashboard view" value={mode} onChange={e => setMode(e.target.value as "MTD" | "YTD")} className="h-8 rounded border px-2 text-xs"><option value="MTD">Selected month</option><option value="YTD">Year to date</option></select>
      <Button size="sm" variant="outline" aria-label="Refresh dashboard" onClick={() => query.refetch()}><RefreshCw size={15} /></Button><Button size="sm" variant="outline" aria-label="Print dashboard" disabled={!data} onClick={() => window.print()}><Printer size={15} /></Button>
    </div></header>
    {query.isPending && <p className="text-sm">Loading financial position…</p>}
    {query.isError && <p role="alert" className="text-sm text-red-700">Financial dashboard could not load. Please retry.</p>}
    {data && <>
      <div className="grid gap-2 sm:grid-cols-4">{(["revenue", "goi", "gop", "nop"] as const).map(key => <Card key={key} className="p-3"><Link to={report("profit-loss")} className="text-xs uppercase text-slate-500">{key === "revenue" ? "Revenue" : key}</Link><div className={`mt-1 text-xl font-semibold tabular-nums ${Number(data[mode][key]) < 0 ? "text-red-700" : "text-slate-900"}`}>{money(data[mode][key])}</div>{data.definitions[key] && <div className="mt-1 text-[10px] text-slate-500">{data.definitions[key]}</div>}</Card>)}</div>
      <div className="grid gap-3 xl:grid-cols-2"><Card className="p-3"><h2 className="mb-2 text-sm font-semibold">Profit & Loss — Monthly vs Cumulative</h2><table className="w-full text-xs"><thead><tr className="border-b"><th className="text-left">Position</th><th className="text-right">Selected month</th><th className="text-right">YTD</th><th className="text-right">% revenue YTD</th></tr></thead><tbody>{rows.map(([key, label]) => <tr key={key} className="border-b"><td className="py-1"><Link title={data.definitions[key]} className="hover:underline" to={report("profit-loss")}>{label}</Link></td><td className="text-right tabular-nums">{money(data.MTD[key])}</td><td className="text-right tabular-nums">{money(data.YTD[key])}</td><td className="text-right">{Number(data.YTD.revenue) ? `${(Number(data.YTD[key]) / Number(data.YTD.revenue) * 100).toFixed(1)}%` : "—"}</td></tr>)}</tbody></table></Card>
      <Card className="p-3"><h2 className="text-sm font-semibold">Revenue, GOI, GOP & NOP trend</h2><div className="h-56"><ResponsiveContainer width="100%" height="100%"><LineChart data={data.monthly.map(row => ({ ...row, month: monthName(row.month), revenue: Number(row.revenue), goi: Number(row.goi), gop: Number(row.gop), nop: Number(row.nop) }))}><CartesianGrid strokeDasharray="3 3" /><XAxis dataKey="month" fontSize={10} /><YAxis fontSize={10} tickFormatter={v => `${(v / 1e6).toFixed(0)}m`} /><Tooltip formatter={v => money(Number(v))} />{["revenue", "goi", "gop", "nop"].map((key, i) => <Line key={key} dataKey={key} stroke={["#2563eb", "#059669", "#d97706", "#7c3aed"][i]} dot={false} strokeWidth={2} />)}</LineChart></ResponsiveContainer></div></Card></div>
      <DepartmentPerformanceTable departments={data.departments} period={mode} asOf={data.as_of_date} locationId={data.scope.location_id} />
      <div className="grid gap-3 md:grid-cols-2">{ranking("Top revenue — selected month", data.top_revenue)}{ranking("Top costs — selected month", data.top_cost)}</div>
      <div className="grid gap-3 md:grid-cols-2"><Card className="p-3"><h2 className="mb-2 text-sm font-semibold">Financial position</h2><table className="w-full text-xs"><tbody>{Object.entries(data.position).map(([key, value]) => <tr key={key} className="border-b"><td className="py-1"><Link to={report("balance-sheet")} className="hover:underline">{key}</Link></td><td className="text-right tabular-nums">{money(value)}</td></tr>)}<tr className={Number(data.balance_gap) ? "font-semibold text-red-700" : "font-semibold text-emerald-700"}><td className="py-1">Assets − Liabilities − Equity</td><td className="text-right">{money(data.balance_gap)}</td></tr></tbody></table></Card>
      <Card className="p-3"><h2 className="mb-2 text-sm font-semibold">Margin performance</h2><div className="grid grid-cols-2 gap-3">{["MTD", "YTD"].map(p => <div key={p}><h3 className="text-xs font-semibold">{p}</h3><p className="mt-2 text-xs">GOP margin: {data[p as "MTD" | "YTD"].gop_margin == null ? "—" : `${Number(data[p as "MTD" | "YTD"].gop_margin).toFixed(1)}%`}</p><p className="text-xs">NOP margin: {data[p as "MTD" | "YTD"].nop_margin == null ? "—" : `${Number(data[p as "MTD" | "YTD"].nop_margin).toFixed(1)}%`}</p></div>)}</div></Card></div>
      {!!data.negative_assets.length && <Card className="p-3"><h2 className="mb-2 text-sm font-semibold">Assets with credit balances</h2><table className="w-full text-xs"><tbody>{data.negative_assets.map(row => <tr key={row.account_ids.join(",")} className="border-b"><td className="py-1"><Link className="text-blue-700" to={`/general-ledger?account_ids=${row.account_ids.join(",")}&date_from=${year}-01-01&date_to=${data.as_of_date}${scope}`}>{row.account_name}</Link></td><td className="text-right text-red-700">{money(row.periods.YTD.current)}</td></tr>)}</tbody></table></Card>}
      <Card className="overflow-x-auto p-3"><h2 className="mb-2 text-sm font-semibold">Monthly performance matrix</h2><table className="w-full whitespace-nowrap text-xs"><thead><tr><th className="text-left">Month</th>{["revenue", "cogs", "goi", "gop", "nop"].map(key => <th key={key} className="text-right uppercase">{key}</th>)}<th className="text-right">GOP %</th><th className="text-right">NOP %</th></tr></thead><tbody>{data.monthly.map(row => <tr key={row.month} className="border-t"><td className="py-1">{monthName(row.month)}</td>{(["revenue", "cogs", "goi", "gop", "nop"] as const).map(key => <td key={key} className="text-right tabular-nums">{money(row[key])}</td>)}<td className="text-right">{row.gop_margin == null ? "—" : Number(row.gop_margin).toFixed(1)}</td><td className="text-right">{row.nop_margin == null ? "—" : Number(row.nop_margin).toFixed(1)}</td></tr>)}</tbody></table></Card>
    </>}
  </section>;
}
