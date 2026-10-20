import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Download, Printer, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import PageHeader from "@/components/common/PageHeader";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import AssetReportFilters, { type AssetFilters } from "./AssetReportFilters";
import { downloadAssetReport, getDepreciationReport } from "./api";
const money = (x: unknown) => Number(x || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export default function DepreciationReportPage() {
  const [filters, setFilters] = useState<AssetFilters>({ status: "POSTED" });
  const q = useQuery({ queryKey: ["depreciation-report", filters], queryFn: () => getDepreciationReport(filters) });
  return <div className="space-y-2"><PageHeader title="Depreciation Report" actions={<><Button variant="outline" aria-label="Refresh" title="Refresh" onClick={() => q.refetch()}><RefreshCw size={15}/></Button><Button variant="outline" aria-label="Export Excel" title="Export Excel" onClick={() => downloadAssetReport("/reports/depreciation/export", filters, "depreciation.xlsx").catch(() => toast.error("Export failed"))}><Download size={15}/></Button><Button variant="outline" aria-label="Print" title="Print" onClick={() => window.print()}><Printer size={15}/></Button></>}/>
    <AssetReportFilters value={filters} onChange={setFilters} depreciation/>
    <div className="flex flex-wrap gap-x-6 text-sm tabular-nums"><span>Posted <b>{money(q.data?.posted_depreciation)}</b></span><span>Planned <b>{money(q.data?.planned_depreciation)}</b></span></div>
    {q.isError && <p role="alert">Could not load depreciation report.</p>}{q.isLoading && <p>Loading…</p>}
    <Table variant="grid" stickyHeader><THead><TR><TH>Asset number</TH><TH>Description</TH><TH>Category</TH><TH>Period</TH><TH className="text-right">Opening</TH><TH className="text-right">Depreciation</TH><TH className="text-right">Accumulated</TH><TH className="text-right">Closing</TH><TH>Journal</TH><TH>Status</TH></TR></THead><TBody>{q.data?.items?.map((x: any) => <TR key={`${x.asset_id}-${x.period}`}><TD><Link className="text-emerald-700 underline" to={`/fixed-assets/${x.asset_id}`}>{x.asset_number}</Link></TD><TD>{x.asset_name}</TD><TD>{x.category}</TD><TD>{x.period}</TD><TD className="text-right tabular-nums">{money(x.opening_book_value)}</TD><TD className="text-right tabular-nums">{money(x.depreciation_amount)}</TD><TD className="text-right tabular-nums">{money(x.accumulated_depreciation)}</TD><TD className="text-right tabular-nums">{money(x.closing_book_value)}</TD><TD>{x.journal_entry_id ? <Link className="text-emerald-700 underline" to={`/journals/${x.journal_entry_id}`}>{x.journal_entry_id}</Link> : "—"}</TD><TD>{x.status}</TD></TR>)}</TBody></Table>
    {!q.isLoading && !q.isError && !q.data?.items?.length && <p>No schedules in this scope and period.</p>}
  </div>;
}
