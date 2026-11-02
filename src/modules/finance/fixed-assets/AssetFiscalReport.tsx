import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Download, Printer, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import AssetReportFilters, { type AssetFilters } from "./AssetReportFilters";
import { downloadAssetReport, getFiscalReport } from "./api";
const money = (n: unknown) => n == null ? "—" : Number(n).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
export default function AssetFiscalReport() {
  const [year, setYear] = useState(new Date().getFullYear());
  const [filters, setFilters] = useState<AssetFilters>({});
  const params = { ...filters, year };
  const q = useQuery({ queryKey: ["asset-fiscal-report", params], queryFn: () => getFiscalReport(params), enabled: year >= 1900 && year <= 9998 });
  const cols = ["opening", "book_depreciation", "fiscal_depreciation", "disposal_value", "closing", "difference"];
  return <div className="space-y-2">
    <div className="flex items-center gap-2 print:hidden"><label className="text-sm">Year <input aria-label="Fiscal year" className="w-24 h-8 rounded border px-2" type="number" min={1900} max={9998} value={year} onChange={e => setYear(Number(e.target.value))}/></label><Button variant="outline" title="Refresh" aria-label="Refresh fiscal report" onClick={() => q.refetch()}><RefreshCw size={15}/></Button><Button variant="outline" title="Export Excel" aria-label="Export fiscal Excel" onClick={() => downloadAssetReport("/reports/fixed-assets-fiscal/export", params, `asset-fiscal-${year}.xlsx`).catch(() => toast.error("Export failed"))}><Download size={15}/></Button><Button variant="outline" title="Print" aria-label="Print fiscal report" onClick={() => window.print()}><Printer size={15}/></Button></div>
    <AssetReportFilters value={filters} onChange={setFilters}/>
    <p className="text-sm">Fiscal comparison {year} · Configured {q.data?.configured ?? "—"} · Not configured / outside fiscal opening {q.data?.unconfigured ?? "—"}</p>
    {q.isLoading && <p>Loading…</p>}{q.isError && <p role="alert">Could not load fiscal comparison.</p>}
    <Table variant="grid" stickyHeader><THead><TR><TH>Asset</TH><TH>Description</TH><TH>Fiscal group</TH><TH>Setup</TH><TH>Fiscal opening</TH><TH>Book depreciation posted</TH><TH>Fiscal depreciation</TH><TH>Fiscal NBV removed on disposal</TH><TH>Fiscal closing</TH><TH>Book − fiscal</TH></TR></THead><TBody>{q.data?.items?.map((r: any) => <TR key={r.id}><TD><Link className="text-emerald-700 underline" to={`/fixed-assets/${r.id}`}>{r.asset_number}</Link></TD><TD>{r.asset_name}</TD><TD>{r.group_code ?? "—"}</TD><TD>{r.status}</TD>{cols.map(k => <TD key={k} className="text-right tabular-nums">{money(r[k])}</TD>)}</TR>)}{q.data && <TR className="font-semibold"><TD colSpan={4}>TOTAL — configured profiles</TD>{cols.map(k => <TD key={k} className="text-right tabular-nums">{money(q.data.totals[k])}</TD>)}</TR>}</TBody></Table>
  </div>;
}
