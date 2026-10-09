import { Fragment } from "react";
import { Link } from "react-router-dom";
import type { Amounts, Period, Row } from "./FinancialReportPage";

export type DepartmentStatement = {
  department_id: number | null;
  department_name: string;
  rows: Row[];
  section_totals: Record<string, Record<Period, Amounts>>;
};
const sections = [["REVENUE", "Pendapatan"], ["COST_OF_REVENUE", "Beban pokok"], ["EXPENSES", "Beban"]] as const;
const metrics = ["current", "budget", "last_month", "last_year", "variance"] as const;
const headings = ["Current", "Budget", "Last month", "Last year", "Variance"];
const money = (value: string | number | null | undefined) => value == null ? "—" : Number(value).toLocaleString("id-ID", { maximumFractionDigits: 2 });

export default function DepartmentStatementTables({ statements, period, asOf, locationId, businessUnitId, printable = false }: {
  statements: DepartmentStatement[]; period: Period; asOf: string;
  locationId?: number | null; businessUnitId?: number | null; printable?: boolean;
}) {
  return <>{statements.map(statement => {
    const ledgerLink = (row: Row) => {
      const query = new URLSearchParams({ date_from: `${asOf.slice(0,4)}-${period === "YTD" ? "01" : asOf.slice(5,7)}-01`, date_to: asOf,
        department_id: String(statement.department_id ?? 0) });
      if (row.account_ids.length === 1) query.set("account_id", String(row.account_ids[0]));
      else query.set("account_ids", row.account_ids.join(","));
      if (locationId) query.set("location_id", String(locationId));
      if (businessUnitId) query.set("business_unit_id", String(businessUnitId));
      return `/general-ledger?${query}`;
    };
    return <section key={statement.department_id ?? "unassigned"} className={`department-statement overflow-x-auto rounded border bg-white p-2 ${printable ? "comparison-page" : ""}`}>
      {printable && <header className="statement-header"><div className="statement-company">PT. MUTIARA MERDEKA HOTEL</div><h1>LAPORAN LABA RUGI — {period}</h1><p>{period === "YTD" ? `${asOf.slice(0,4)}-01-01` : `${asOf.slice(0,7)}-01`} — {asOf} · Rupiah (IDR)</p></header>}
      <h2 className="mb-2 text-sm font-semibold">{statement.department_name} — {period}</h2>
      <table className={`w-full text-xs ${printable ? "" : "whitespace-nowrap"}`}><thead><tr><th className="px-2 py-1 text-left">Account</th>{headings.map(heading => <th key={heading} className="px-2 py-1 text-right">{heading}</th>)}</tr></thead><tbody>
        {sections.map(([section, label]) => <Fragment key={section}>
          <tr className="border-y bg-slate-50 font-semibold"><td className="px-2 py-1">{label}</td>{metrics.map(metric => <td key={metric} className="px-2 py-1 text-right tabular-nums">{money(statement.section_totals[section]?.[period]?.[metric])}</td>)}</tr>
          {statement.rows.filter(row => row.section === section).map(row => <tr key={`${row.account_code}-${row.account_name}`} className="border-b"><td className={printable ? "account px-2 py-1" : "max-w-[22rem] truncate px-2 py-1"} title={row.account_name}>{printable || !row.account_ids.length ? row.account_name : <Link className="text-blue-700 hover:underline" to={ledgerLink(row)}>{row.account_name}</Link>}</td>{metrics.map(metric => <td key={metric} className="px-2 py-1 text-right tabular-nums">{money(row.periods[period][metric])}</td>)}</tr>)}
        </Fragment>)}
        <tr className="border-t-2 bg-slate-100 font-bold"><td className="px-2 py-1">Laba / Rugi</td>{metrics.map(metric => {
          const values = sections.map(([section]) => statement.section_totals[section]?.[period]?.[metric]);
          const result = values.some(value => value == null) ? null : Number(values[0]) - Number(values[1]) - Number(values[2]);
          return <td key={metric} className={`px-2 py-1 text-right tabular-nums ${result != null && result < 0 ? "text-red-700" : ""}`}>{money(result)}</td>;
        })}</tr>
      </tbody></table>
    </section>;
  })}</>;
}
