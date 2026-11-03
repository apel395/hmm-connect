import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Pagination from "@/components/datatable/Pagination";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { useReceivedItemHistory } from "../hooks/useGoodsReceipts";

const amount = (value: number) => Number(value).toLocaleString("id-ID", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const date = (value: string) => new Date(value).toLocaleDateString("id-ID", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "Asia/Jakarta",
});

export default function ReceivedItemHistorySearch() {
  const navigate = useNavigate();
  const [search, setSearch] = useState("");
  const [term, setTerm] = useState("");
  const [page, setPage] = useState(1);
  useEffect(() => {
    const timer = window.setTimeout(() => {
      setTerm(search.trim());
      setPage(1);
    }, 300);
    return () => window.clearTimeout(timer);
  }, [search]);

  const results = useReceivedItemHistory(term, page);
  const rows = results.data?.items ?? [];
  const total = results.data?.total_items ?? 0;

  return <Card className="overflow-hidden p-0">
    <div className="space-y-2 border-b p-3">
      <h2 className="text-sm font-semibold text-slate-900">Find Received Item</h2>
      <p className="text-xs text-slate-500">Search historical Receiving lines by item name or code to find its RR date and purchase cost.</p>
      <div className="flex items-center gap-2 rounded-md border border-slate-300 bg-white px-3">
        <Search size={16} className="shrink-0 text-slate-500" aria-hidden="true" />
        <input
          aria-label="Search received item"
          placeholder="Item name or code, e.g. BLANDER PHILIPS"
          className="h-10 min-w-0 flex-1 bg-transparent text-sm outline-none"
          value={search}
          onChange={(event) => setSearch(event.target.value)}
        />
        {search && <button type="button" aria-label="Clear item search" className="text-slate-500" onClick={() => { setSearch(""); setTerm(""); setPage(1); }}><X size={16} /></button>}
      </div>
    </div>
    {term.length >= 2 && <>
      {results.isLoading ? <p className="p-4 text-sm text-slate-500">Searching received items...</p>
        : results.isError ? <p role="alert" className="p-4 text-sm text-red-700">Received item history could not be loaded.</p>
          : <>
            <Table className="min-w-[1050px]" containerClassName="rounded-none border-0 shadow-none">
              <THead><TR><TH>Item</TH><TH>Receiving / RR Date</TH><TH>Supplier</TH><TH numeric>Received Qty</TH><TH numeric>Unit Cost</TH><TH numeric>Line Total</TH><TH>Status</TH><TH numeric>Action</TH></TR></THead>
              <TBody>
                {rows.map((line) => <TR key={line.goods_receipt_item_id}>
                  <TD><TableCellStack primary={line.product_name} secondary={line.product_code} /></TD>
                  <TD><TableCellStack primary={line.receipt_number} secondary={date(line.received_at)} /></TD>
                  <TD>{line.supplier_name || "—"}</TD>
                  <TD numeric>{Number(line.quantity).toLocaleString("id-ID")} {line.uom ?? ""}</TD>
                  <TD numeric>{amount(line.unit_cost)}</TD>
                  <TD numeric>{amount(line.line_subtotal)}</TD>
                  <TD><Badge variant={line.status === "POSTED" ? "success" : "outline"}>{line.status}</Badge></TD>
                  <TD numeric><Button size="sm" variant="outline" onClick={() => navigate(`/receiving/${line.goods_receipt_id}`)}>View RR</Button></TD>
                </TR>)}
              </TBody>
            </Table>
            {!rows.length && <p className="p-4 text-center text-sm text-slate-500">No received items match this search.</p>}
            {total > 0 && <div className="px-3 pb-3"><Pagination page={page} pages={results.data?.total_pages ?? 0} total={total} pageSize={50} noun="received item lines" onChange={setPage} /></div>}
          </>}
    </>}
  </Card>;
}
