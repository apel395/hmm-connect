import { Fragment } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import DepartmentPerformanceTable from "./DepartmentPerformanceTable";
import api from "@/api/client";
import useAuthStore from "@/store/auth";
import type { Kind, Period, Amounts, Row, Report } from "./FinancialReportPage";

const labels: Record<string, string> = { REVENUE: "Pendapatan", COST_OF_REVENUE: "Beban Pokok", EXPENSES: "Beban", ASSETS: "Aset", LIABILITIES: "Liabilitas", EQUITY: "Ekuitas" };
const metrics: (keyof Amounts)[] = ["current", "budget", "last_month", "last_year", "variance"];
const metricNames = ["Current", "Budget", "Last Month", "Last Year", "Variance"];
const money = (value: string | number | null | undefined) => value == null ? "—" : Number(value).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const sum = (data: Report, sections: string[], period: Period, metric: keyof Amounts) => {
  const values = sections.map(section => data.section_totals[section]?.[period]?.[metric]);
  return values.some(value => value == null) ? null : values.reduce<number>((total, value) => total + Number(value), 0);
};
const profit = (data: Report, period: Period, metric: keyof Amounts) => {
  const revenue = sum(data, ["REVENUE"], period, metric), costs = sum(data, ["COST_OF_REVENUE", "EXPENSES"], period, metric);
  return revenue == null || costs == null ? null : revenue - costs;
};

const css = `
@page { size: A4 landscape; margin: 10mm 10mm 14mm; @bottom-left { content: "MMH-Connect · IDR"; font: 8pt Arial; } @bottom-right { content: "Page " counter(page); font: 8pt Arial; } }
.statement-print { color:#111; font: 9pt Arial, sans-serif; background:white; margin:auto; padding:10mm; }
.statement-header { text-align:center; border-bottom:2px solid #222; margin-bottom:4mm; padding-bottom:3mm; break-inside:avoid; }
.statement-header h1 { font-size:14pt; margin:2mm 0; }.statement-header p { margin:1mm 0; }.statement-company { font-weight:bold; font-size:11pt; }
.statement-print table { width:100%; border-collapse:collapse; font-size:8pt; }.statement-print th,.statement-print td { padding:1.2mm 1mm; vertical-align:top; border-bottom:1px solid #ddd; }
.statement-print th { border-bottom:1px solid #222; }.statement-print thead { display:table-header-group; }.statement-print tr { break-inside:avoid; page-break-inside:avoid; }
.statement-print .amount { text-align:right; white-space:nowrap; font-variant-numeric:tabular-nums; }.statement-print .account { text-align:left; overflow-wrap:anywhere; min-width:45mm; }
.statement-print .group { font-weight:bold; border-top:1px solid #222; background:#f3f3f3; }.statement-print .total { font-weight:bold; border-top:1px solid #222; }.statement-print .grand-total { font-weight:bold; border-top:2px solid #222; border-bottom:3px double #222; }
.statement-t { display:grid; grid-template-columns:minmax(0,1fr) minmax(0,1fr); gap:7mm; }.statement-t > table { align-self:start; }.statement-print .comparison-page { break-before:page; page-break-before:always; margin-top:10mm; }
.statement-print .print-meta { font-size:8pt; margin-top:4mm; }.statement-print .period-range { font-size:7pt; font-weight:normal; display:block; white-space:nowrap; }
@media print { html,body,#root { background:white!important; margin:0!important; padding:0!important; overflow:visible!important; height:auto!important; }.statement-print { padding:0; }.statement-print .comparison-page { margin-top:0; } }
`;

function ReportHeader({ kind, data, asOf, caption }: { kind: Kind; data: Report; asOf: string; caption?: string }) {
  const scope = Object.entries(data.scope).filter(([, value]) => value != null).map(([key]) => data.scope_labels?.[key]).filter(Boolean).join(" · ") || "Konsolidasi";
  return <header className="statement-header"><div className="statement-company">PT. MUTIARA MERDEKA HOTEL</div><h1>{kind === "PROFIT_LOSS" ? "LAPORAN LABA RUGI" : "NERACA"}{data.header_only ? " — KAP" : ""}</h1>
    <p>{kind === "BALANCE_SHEET" ? `Per ${asOf}` : `Periode sampai ${asOf}`} · {scope} · Rupiah (IDR)</p>{caption ? <p>{caption}</p> : null}</header>;
}

function SectionRows({ data, sections, periods, columns }: { data: Report; sections: string[]; periods: Period[]; columns: (keyof Amounts)[] }) {
  return <>{sections.map(section => <Fragment key={section}>
    <tr className="group"><td colSpan={1 + periods.length * columns.length}>{labels[section]}</td></tr>
    {data.rows.filter(row => row.section === section).map((row: Row) => <tr key={`${row.account_code}-${row.account_name}`}><td className="account">{row.account_name}</td>{periods.flatMap(period => columns.map(metric => <td className="amount" key={`${period}-${metric}`}>{money(row.periods[period][metric])}</td>))}</tr>)}
    <tr className="total"><td className="account">Total {labels[section]}</td>{periods.flatMap(period => columns.map(metric => <td className="amount" key={`${period}-${metric}`}>{money(data.section_totals[section]?.[period]?.[metric])}</td>))}</tr>
  </Fragment>)}</>;
}

export function FinancialStatementPrint({ kind, data, asOf, printedBy }: { kind: Kind; data: Report; asOf: string; printedBy?: string }) {
  const comparisons = [...metrics, "movement" as const];
  const metadata = <div className="print-meta">{printedBy ? `Dicetak oleh ${printedBy} · ` : ""}{new Date().toLocaleString("id-ID")} · MMH-Connect</div>;
  return <article className="statement-print print-document" data-print-ready="true"><style>{css}</style><ReportHeader kind={kind} data={data} asOf={asOf} />
    {kind === "PROFIT_LOSS" ? <table><thead><tr><th className="account" rowSpan={2}>Akun</th>{(["MTD", "YTD"] as const).map(period => <th key={period} colSpan={metrics.length}>{period}<span className="period-range">{data.periods[period].current?.join(" — ")}</span></th>)}</tr><tr>{["MTD", "YTD"].flatMap(period => metricNames.map(name => <th className="amount" key={`${period}-${name}`}>{name}</th>))}</tr></thead><tbody>
      <SectionRows data={data} sections={["REVENUE", "COST_OF_REVENUE", "EXPENSES"]} periods={["MTD", "YTD"]} columns={metrics} />
      <tr className="grand-total"><td>Laba / Rugi</td>{(["MTD", "YTD"] as const).flatMap(period => metrics.map(metric => <td className="amount" key={`${period}-${metric}`}>{money(profit(data, period, metric))}</td>))}</tr>
    </tbody></table> : <>
      <div className="statement-t">{[["ASSETS"], ["LIABILITIES", "EQUITY"]].map(sections => <table key={sections[0]}><thead><tr><th className="account">Akun</th><th className="amount">Saldo per {asOf}</th></tr></thead><tbody><SectionRows data={data} sections={sections} periods={["YTD"]} columns={["current"]} />{sections.includes("LIABILITIES") ? <tr className="grand-total"><td>Total Liabilitas + Ekuitas</td><td className="amount">{money(sum(data, sections, "YTD", "current"))}</td></tr> : null}</tbody></table>)}</div>
      {metadata}
      {(["MTD", "YTD"] as const).map(period => <section className="comparison-page" key={period}><ReportHeader kind={kind} data={data} asOf={asOf} caption={`Perbandingan ${period}`} /><table><thead><tr><th className="account">Akun</th>{[...metricNames, "Movement"].map((name, i) => <th className="amount" key={name}>{name}{data.periods[period][comparisons[i]] ? <span className="period-range">{data.periods[period][comparisons[i]].join(" — ")}</span> : null}</th>)}</tr></thead><tbody><SectionRows data={data} sections={["ASSETS", "LIABILITIES", "EQUITY"]} periods={[period]} columns={comparisons} /><tr className="grand-total"><td>Total Liabilitas + Ekuitas</td>{comparisons.map(metric => <td key={metric} className="amount">{money(sum(data, ["LIABILITIES", "EQUITY"], period, metric))}</td>)}</tr></tbody></table>{metadata}</section>)}
    </>}{kind === "PROFIT_LOSS" ? metadata : null}
    {kind === "PROFIT_LOSS" && data.departments && <>{(["MTD", "YTD"] as const).map(period => <DepartmentPerformanceTable key={period} departments={data.departments ?? []} period={period} asOf={asOf} locationId={data.scope.location_id} businessUnitId={data.scope.business_unit_id} />)}</>}
  </article>;
}

export default function FinancialReportPrintPage({ kind }: { kind: Kind }) {
  const [search] = useSearchParams();
  const user = useAuthStore(state => state.user);
  const params = Object.fromEntries(search);
  const asOf = search.get("as_of_date") || new Date().toLocaleDateString("en-CA");
  const query = useQuery({ queryKey: ["financial-report-print", kind, params], queryFn: async () => (await api.get<Report>("/financial-reports/comparison", { params: { ...params, report_type: kind, as_of_date: asOf } })).data });
  if (query.isPending) return <p data-print-ready="false">Loading report…</p>;
  if (query.isError) return <p data-print-ready="false" role="alert">Report could not be loaded. Close this preview and try again.</p>;
  return <FinancialStatementPrint kind={kind} data={query.data} asOf={asOf} printedBy={user?.full_name || user?.username} />;
}
