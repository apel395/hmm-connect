type Props = { title: string; context: string; rows?: number; total?: number };

export default function InventoryReportHeading({ title, context, rows, total }: Props) {
  return <div className="inventory-report-heading hidden print:block">
    <div className="text-xs font-semibold">MMH-Connect</div>
    <h1 className="text-lg font-bold">{title}</h1>
    <div className="text-xs">{context}</div>
    {rows !== undefined && <div className="text-xs">Showing {rows} of {total ?? rows} records · Totals cover the selected filters</div>}
  </div>;
}
