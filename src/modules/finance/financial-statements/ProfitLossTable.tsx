import { useState } from "react";
import { Link } from "react-router-dom";
import Dialog, { DialogContent, DialogTitle } from "../../../components/ui/Dialog";
import type { Amounts, Period, Report } from "./FinancialReportPage";

export type PresentationRow = { key: string; label: string; kind: "category" | "detail" | "subtotal"; account_ids: number[]; periods: Record<Period, Amounts> };
export type RelatedAccount = { account_id: number; account_code: string; account_name: string; category: string; periods: Record<Period, Amounts> };
const metrics = ["current", "budget", "last_month", "last_year", "variance"] as const;
const names = ["Current", "Budget", "Last month", "Last year", "Variance"];
const money = (value: string | number | null | undefined) => value == null ? "—" : Number(value).toLocaleString("id-ID", { maximumFractionDigits: 2 });
export default function ProfitLossTable({ data, periods, asOf, printable = false }: { data: Report; periods: Period[]; asOf: string; printable?: boolean }) {
  const [selected, setSelected] = useState<PresentationRow | null>(null);
  const rows = (data.presentation_rows ?? []).filter(row => row.kind !== "detail");
  const accounts = (data.related_accounts ?? []).filter(account => selected?.account_ids.includes(account.account_id));
  const link = (account: RelatedAccount, period: Period) => {
    const query = new URLSearchParams({ date_from: `${asOf.slice(0,4)}-${period === "YTD" ? "01" : asOf.slice(5,7)}-01`, date_to: asOf, account_id: String(account.account_id) });
    for (const key of ["location_id", "business_unit_id", "department_id"] as const) if (data.scope[key] != null) query.set(key, String(data.scope[key]));
    return `/general-ledger?${query}`;
  };
  const header = (withCode = false) => <><tr>{withCode && <th rowSpan={2} className="px-2 py-1 text-left">Code</th>}<th className="account px-2 py-1 text-left" rowSpan={2}>Name</th>{periods.map(period => <th key={period} colSpan={metrics.length} className="px-2 py-1">{period}</th>)}</tr><tr>{periods.flatMap(period => names.map(name => <th key={`${period}-${name}`} className="amount px-2 py-1 text-right">{name}</th>))}</tr></>;
  return <><div className={printable ? "" : "max-h-[65vh] overflow-auto rounded border bg-white"}><table className={`w-full text-xs ${printable ? "" : "table-standard whitespace-nowrap"}`}><thead className={printable ? "" : "sticky top-0 z-10 bg-slate-100"}>{header()}</thead><tbody>{rows.map(row => <tr key={row.key} className={row.kind === "subtotal" ? "grand-total border-y-2 bg-slate-100 font-bold" : "group border-y bg-slate-50 font-semibold"}><td className="account px-2 py-1">{printable ? row.label : <button type="button" className="text-blue-700 hover:underline" onClick={() => setSelected(row)} aria-label={`Show accounts for ${row.label}`}>{row.label}</button>}</td>{periods.flatMap(period => metrics.map(metric => <td key={`${period}-${metric}`} className={`amount px-2 py-1 text-right tabular-nums ${Number(row.periods[period][metric]) < 0 ? "text-red-700" : ""}`}>{money(row.periods[period][metric])}</td>))}</tr>)}</tbody></table></div>
  {!printable && <Dialog open={selected !== null} onOpenChange={open => { if (!open) setSelected(null); }}><DialogContent className="max-w-[95vw]"><DialogTitle className="px-4 py-3 font-semibold">{selected?.label}</DialogTitle><div className="overflow-auto px-4 pb-4"><table className="table-standard w-full whitespace-nowrap text-xs"><thead className="sticky top-0 bg-slate-100">{header(true)}</thead><tbody>{accounts.map(account => <tr key={account.account_id} className="border-b"><td className="px-2 py-1">{account.account_code}</td><td className="px-2 py-1">{account.account_name}</td>{periods.flatMap(period => metrics.map(metric => {
    const value = account.periods[period][metric];
    const effect = selected?.kind === "subtotal" && account.category !== "REVENUE" && value != null ? -Number(value) : value;
    return <td key={`${period}-${metric}`} className={`px-2 py-1 text-right tabular-nums ${Number(effect) < 0 ? "text-red-700" : ""}`}><Link className="hover:underline" to={link(account, period)}>{money(effect)}</Link></td>;
  }))}</tr>)}</tbody></table>{accounts.length === 0 && <p className="py-4 text-sm text-slate-500">No related accounts configured.</p>}</div></DialogContent></Dialog>}
  </>;
}
