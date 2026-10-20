import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Download, Printer, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import PageHeader from "@/components/common/PageHeader";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import AssetReportFilters, { type AssetFilters } from "./AssetReportFilters";
import { downloadAssetReport, getAssetReport } from "./api";
const money = (x: unknown) => x == null ? "—" : Number(x).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export default function FixedAssetReportPage() {
  const [filters, setFilters] = useState<AssetFilters>({});
  const q = useQuery({ queryKey: ["fixed-asset-report", filters], queryFn: () => getAssetReport(filters) });
  const totals = q.data?.totals;
  return <div className="space-y-2">
    <PageHeader title="Fixed Asset Register" actions={<><Button variant="outline" aria-label="Refresh" title="Refresh" onClick={() => q.refetch()}><RefreshCw size={15}/></Button><Button variant="outline" aria-label="Export Excel" title="Export Excel" onClick={() => downloadAssetReport("/reports/fixed-assets/export", filters, "fixed-assets.xlsx").catch(() => toast.error("Export failed"))}><Download size={15}/></Button><Button variant="outline" aria-label="Print" title="Print" onClick={() => window.print()}><Printer size={15}/></Button></>}/>
    <AssetReportFilters value={filters} onChange={setFilters}/>
    <div className="flex flex-wrap gap-x-6 gap-y-1 text-sm tabular-nums"><span>Cost <b>{money(totals?.acquisition_cost)}</b></span><span>Accumulated depreciation <b>{money(totals?.accumulated_depreciation)}</b></span><span>Net book value <b>{money(totals?.net_book_value)}</b></span></div>
    {q.isError && <p role="alert">Could not load asset report.</p>}
    {q.isLoading && <p>Loading…</p>}
    <Table variant="grid" stickyHeader><THead><TR><TH>Asset number</TH><TH>Description</TH><TH>Category</TH><TH>Acquired</TH><TH>Life (months)</TH><TH className="text-right">Cost</TH><TH className="text-right">Accumulated</TH><TH className="text-right">Net book value</TH><TH>Status</TH><TH>Policy review</TH></TR></THead><TBody>{q.data?.items?.map((x: any) => <TR key={x.id}><TD><Link className="text-emerald-700 underline" to={`/fixed-assets/${x.id}`}>{x.asset_number}</Link></TD><TD>{x.asset_name}</TD><TD>{x.category}</TD><TD>{x.acquisition_date}</TD><TD>{x.useful_life_months ?? "—"}</TD><TD className="text-right tabular-nums">{money(x.acquisition_cost)}</TD><TD className="text-right tabular-nums">{money(x.accumulated_depreciation)}</TD><TD className="text-right tabular-nums">{money(x.net_book_value)}</TD><TD>{x.status}</TD><TD className="text-amber-700">{x.policy_review ? "Review useful life" : "—"}</TD></TR>)}</TBody></Table>
    {!q.isLoading && !q.isError && !q.data?.items?.length && <p>No registered assets in this scope.</p>}
  </div>;
}
