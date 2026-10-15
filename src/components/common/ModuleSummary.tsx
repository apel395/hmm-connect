export interface SummaryMetric { label: string; value: string | number; note?: string }

export default function ModuleSummary({ metrics }: { metrics: SummaryMetric[] }) {
  return <section aria-label="Page summary" className="flex flex-wrap items-center gap-x-5 gap-y-1 rounded border border-slate-200 bg-white px-2 py-1 text-xs">
    {metrics.map(metric => <span key={metric.label} title={metric.note} className="inline-flex items-baseline gap-2 whitespace-nowrap"><span className="text-slate-500">{metric.label}</span><strong className="font-semibold tabular-nums text-slate-900">{metric.value}</strong></span>)}
  </section>;
}
