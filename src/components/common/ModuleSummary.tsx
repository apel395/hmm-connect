import Card from "@/components/ui/Card";

export interface SummaryMetric { label:string; value:string | number; note?:string }

export default function ModuleSummary({metrics}:{metrics:SummaryMetric[]}) {
  return <section aria-label="Page summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
    {metrics.map((metric) => <Card key={metric.label} className="p-5">
      <p className="text-sm font-medium text-slate-500">{metric.label}</p>
      <p className="mt-2 text-2xl font-semibold text-slate-900">{metric.value}</p>
      {metric.note && <p className="mt-1 text-xs text-slate-500">{metric.note}</p>}
    </Card>)}
  </section>;
}
