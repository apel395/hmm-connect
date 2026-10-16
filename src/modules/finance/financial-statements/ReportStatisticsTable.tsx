import type { Period } from './FinancialReportPage';

const metrics = ['current','budget','last_month','last_year','variance'] as const;
type Metric = typeof metrics[number];
export type StatisticRow = {
  key: string; label: string; format: 'number' | 'percent' | 'money'; unit: string | null;
  periods: Record<Period, Record<Metric, string | number | null>>;
  issues?: Partial<Record<Period, Partial<Record<Metric, string>>>>;
};
export type ReportStatistics = { available: boolean; rows: StatisticRow[] };

function formatted(row: StatisticRow, value: string | number | null) {
  if(value == null) return '—';
  const amount = Number(value) * (row.format === 'percent' ? 100 : 1);
  return amount.toLocaleString('id-ID',{maximumFractionDigits:row.format === 'number' ? 4 : 2}) + (row.format === 'percent' ? '%' : '');
}

export default function ReportStatisticsTable({data,periods,printable=false}:{data?:ReportStatistics;periods:Period[];printable?:boolean}){
  if(!data?.rows.length)return null;
  const table=<table className="w-full whitespace-nowrap text-xs"><thead className="bg-slate-100"><tr><th rowSpan={2} className="account px-2 py-1 text-left">Metric / Unit</th>{periods.map(p=><th key={p} colSpan={5} className="px-2 py-1">{p}</th>)}</tr><tr>{periods.flatMap(p=>['Current','Statistics budget','Last month','Last year','Variance vs budget'].map(label=><th key={`${p}-${label}`} className="amount px-2 py-1 text-right">{label}</th>))}</tr></thead><tbody>{data.rows.map(row=><tr key={row.key} className="border-b"><td className="account px-2 py-1 font-medium">{row.label}{row.unit&&row.format!=='percent'?` (${row.unit})`:''}</td>{periods.flatMap(p=>metrics.map(m=><td key={`${p}-${m}`} title={row.issues?.[p]?.[m]} className="amount px-2 py-1 text-right tabular-nums">{formatted(row,row.periods[p][m])}</td>))}</tr>)}</tbody></table>;
  if(printable)return <section className="mb-3"><h2 className="mb-1 font-semibold">Operating Statistics</h2>{table}</section>;
  return <details open className="shrink-0 rounded border bg-white text-xs"><summary className="cursor-pointer px-2 py-1.5 font-semibold">Operating Statistics</summary><div className="overflow-auto">{table}</div></details>;
}
