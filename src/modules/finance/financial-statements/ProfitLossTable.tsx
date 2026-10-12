import { Link } from "react-router-dom";
import type { Amounts, Period, Report } from "./FinancialReportPage";

export type PresentationRow = { key: string; label: string; kind: "category" | "detail" | "subtotal"; account_ids: number[]; periods: Record<Period, Amounts> };
const metrics = ["current", "budget", "last_month", "last_year", "variance"] as const;
const names = ["Current", "Budget", "Last month", "Last year", "Variance"];
const money = (value: string | null | undefined) => value == null ? "—" : Number(value).toLocaleString("id-ID", { maximumFractionDigits: 2 });
export default function ProfitLossTable({ data, periods, asOf, printable = false }: { data: Report; periods: Period[]; asOf: string; printable?: boolean }) {
  const rows = data.presentation_rows ?? [];
  const link = (row: PresentationRow) => {
    const query = new URLSearchParams({ date_from: `${asOf.slice(0,4)}-${periods[0] === "YTD" ? "01" : asOf.slice(5,7)}-01`, date_to: asOf, account_ids: row.account_ids.join(",") });
    for (const key of ["location_id", "business_unit_id", "department_id"] as const) if (data.scope[key] != null) query.set(key, String(data.scope[key]));
    return `/general-ledger?${query}`;
  };
  return <div className={printable ? "" : "max-h-[65vh] overflow-auto rounded border bg-white"}><table className={`w-full text-xs ${printable ? "" : "table-standard whitespace-nowrap"}`}><thead className={printable ? "" : "sticky top-0 z-10 bg-slate-100"}><tr><th className="account px-2 py-1 text-left" rowSpan={2}>Name</th>{periods.map(period => <th key={period} colSpan={metrics.length} className="px-2 py-1">{period}</th>)}</tr><tr>{periods.flatMap(period => names.map(name => <th key={`${period}-${name}`} className="amount px-2 py-1 text-right">{name}</th>))}</tr></thead><tbody>{rows.map(row => <tr key={row.key} className={row.kind === "subtotal" ? "grand-total border-y-2 bg-slate-100 font-bold" : row.kind === "category" ? "group border-y bg-slate-50 font-semibold" : "border-b"}><td className={`account px-2 py-1 ${row.kind === "detail" ? "pl-4" : ""}`}>{!printable && row.account_ids.length ? <Link className="text-blue-700 hover:underline" to={link(row)}>{row.label}</Link> : row.label}</td>{periods.flatMap(period => metrics.map(metric => <td key={`${period}-${metric}`} className={`amount px-2 py-1 text-right tabular-nums ${Number(row.periods[period][metric]) < 0 ? "text-red-700" : ""}`}>{money(row.periods[period][metric])}</td>))}</tr>)}</tbody></table></div>;
}
