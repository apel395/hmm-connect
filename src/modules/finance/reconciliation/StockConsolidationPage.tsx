import { useMemo, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import api from "@/api/client";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import SearchableSelect from "@/components/form/SearchableSelect";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { listLocations } from "@/modules/admin/organization/api";
import { warehouseApi } from "@/modules/master/warehouses/api/warehouseApi";

type StockRow = {
  id: number;
  product_id: number;
  product_code: string;
  product_name: string;
  uom: string;
  location_id?: number | null;
  location_name?: string | null;
  warehouse_id?: number | null;
  warehouse_name?: string | null;
  closing_2025_qty: number | string;
  excluded_pre2026_receiving_qty: number | string;
  opening_2026_qty: number | string;
  current_qty: number | string;
  variance_qty: number | string;
  request_qty?: number | string | null;
  request_status?: string | null;
  status: string;
};

type StockResponse = {
  items: StockRow[];
  summary: {
    item_count: number;
    opening_qty: number | string;
    current_qty: number | string;
    variance_qty: number | string;
    pending_requests: number;
  };
  page: number;
  total_items: number;
  has_next: boolean;
  has_previous: boolean;
};

const qty = (value: unknown) => Number(value || 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });

export default function StockConsolidationPage() {
  const [page, setPage] = useState(1);
  const [requestRow, setRequestRow] = useState<StockRow | null>(null);
  const [requestQty, setRequestQty] = useState("");
  const [requestNote, setRequestNote] = useState("");
  const [filters, setFilters] = useState({
    fiscal_year: 2026,
    location_id: undefined as number | undefined,
    warehouse_id: undefined as number | undefined,
    search: "",
    status: "",
  });

  const locations = useQuery({ queryKey: ["stock-consolidation-locations"], queryFn: () => listLocations({ is_active: true }) });
  const warehouses = useQuery({ queryKey: ["stock-consolidation-warehouses"], queryFn: async () => (await warehouseApi.list()).data });
  const query = useQuery({
    queryKey: ["stock-consolidation", filters, page],
    queryFn: async () => (await api.get<StockResponse>("/stock-reconciliation", { params: { ...filters, location_id: filters.location_id || undefined, warehouse_id: filters.warehouse_id || undefined, status: filters.status || undefined, search: filters.search || undefined, page, page_size: 50 } })).data,
  });

  const rows = useMemo(() => query.data?.items ?? [], [query.data?.items]);
  const pageVariance = useMemo(() => rows.reduce((sum, row) => sum + Number(row.variance_qty || 0), 0), [rows]);

  const request = useMutation({
    mutationFn: async () => {
      if (!requestRow) return;
      await api.post("/stock-reconciliation/requests", {
        product_id: requestRow.product_id,
        warehouse_id: requestRow.warehouse_id,
        fiscal_year: filters.fiscal_year,
        requested_qty: Number(requestQty || 0),
        notes: requestNote || undefined,
      });
    },
    onSuccess: () => {
      toast.success("Opening stock adjustment request submitted.");
      setRequestRow(null);
      setRequestQty("");
      setRequestNote("");
      query.refetch();
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Adjustment request could not be submitted."),
  });

  const locationOptions = (locations.data ?? []).map((row: any) => ({
    id: row.id,
    label: row.code + " — " + row.name,
    keywords: [row.code ?? "", row.name ?? ""],
  }));
  const warehouseOptions = (warehouses.data ?? []).map((row: any) => ({
    id: row.id,
    label: row.code + " — " + row.name,
    keywords: [row.code ?? "", row.name ?? ""],
  }));

  return (
    <div className="space-y-5">
      <PageHeader
        title="Stock Consolidation"
        description="Reconcile 2026 opening stock against source ending stock while excluding pre-2026 receiving."
        actions={<div className="flex gap-2"><Link className="inline-flex h-9 items-center rounded-md border px-3 text-sm font-medium" to="/financial-reconciliation">Financial Controls</Link><Button>Stock Consolidation</Button></div>}
      />

      <Card className="border-amber-200 bg-amber-50/50">
        <div className="grid gap-3 md:grid-cols-3">
          <div><div className="text-xs font-medium uppercase tracking-wide text-amber-700">Cutoff Rule</div><div className="mt-1 font-semibold">Start stock from 01-01-2026</div></div>
          <div><div className="text-xs font-medium uppercase tracking-wide text-amber-700">Historical Receiving</div><div className="mt-1 font-semibold">Receiving dated 2025 is excluded</div></div>
          <div><div className="text-xs font-medium uppercase tracking-wide text-amber-700">Opening Basis</div><div className="mt-1 font-semibold">2025 ending stock → 2026 opening stock</div></div>
        </div>
      </Card>

      <Card>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <label className="text-sm">Fiscal Year<Input type="number" min={2026} className="mt-1" value={filters.fiscal_year} onChange={(e) => { setFilters({ ...filters, fiscal_year: Number(e.target.value) || 2026 }); setPage(1); }} /></label>
          <SearchableSelect label="Location" value={filters.location_id} placeholder="All locations" options={locationOptions} onChange={(location_id) => { setFilters({ ...filters, location_id }); setPage(1); }} />
          <SearchableSelect label="Warehouse" value={filters.warehouse_id} placeholder="All warehouses" options={warehouseOptions} onChange={(warehouse_id) => { setFilters({ ...filters, warehouse_id }); setPage(1); }} />
          <label className="text-sm">Status<select className="mt-1 h-10 w-full rounded-md border px-3" value={filters.status} onChange={(e) => { setFilters({ ...filters, status: e.target.value }); setPage(1); }}><option value="">All statuses</option><option value="MATCHED">Matched</option><option value="VARIANCE">Variance</option><option value="REQUESTED">Adjustment Requested</option></select></label>
          <label className="text-sm">Search<Input className="mt-1" placeholder="Item code or name" value={filters.search} onChange={(e) => { setFilters({ ...filters, search: e.target.value }); setPage(1); }} /></label>
        </div>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Items" value={String(query.data?.summary?.item_count ?? 0)} />
        <Metric label="Opening Qty" value={qty(query.data?.summary?.opening_qty)} />
        <Metric label="Current Qty" value={qty(query.data?.summary?.current_qty)} />
        <Metric label="Variance Qty" value={qty(query.data?.summary?.variance_qty)} />
        <Metric label="Pending Requests" value={String(query.data?.summary?.pending_requests ?? 0)} />
      </div>

      <Card className="p-0">
        {query.isLoading ? <div className="p-10 text-center text-sm text-slate-500">Loading stock consolidation…</div> : query.isError ? <div className="p-10 text-center text-sm text-amber-700">Stock consolidation endpoint is not available yet.</div> : <>
          <Table variant="grid" className="min-w-[1280px]">
            <THead><TR><TH>Item</TH><TH>Warehouse</TH><TH numeric>2025 Ending</TH><TH numeric>Excluded 2025 Receiving</TH><TH numeric>2026 Opening</TH><TH numeric>Current Stock</TH><TH numeric>Variance</TH><TH>Request</TH><TH>Status</TH></TR></THead>
            <TBody>{rows.map((row) => <TR key={row.id}>
              <TD><TableCellStack primary={row.product_name} secondary={row.product_code + " · " + row.uom} /></TD>
              <TD><TableCellStack primary={row.warehouse_name || "—"} secondary={row.location_name || undefined} /></TD>
              <TD numeric>{qty(row.closing_2025_qty)}</TD>
              <TD numeric>{qty(row.excluded_pre2026_receiving_qty)}</TD>
              <TD numeric className="font-semibold">{qty(row.opening_2026_qty)}</TD>
              <TD numeric>{qty(row.current_qty)}</TD>
              <TD numeric className={Number(row.variance_qty || 0) === 0 ? "text-emerald-700" : "font-semibold text-amber-700"}>{qty(row.variance_qty)}</TD>
              <TD>{row.request_status ? <TableCellStack primary={row.request_status} secondary={row.request_qty ? "Qty " + qty(row.request_qty) : undefined} /> : <Button size="xs" variant="outline" onClick={() => { setRequestRow(row); setRequestQty(String(Math.abs(Number(row.variance_qty || 0)))); }}>Request Adjustment</Button>}</TD>
              <TD>{row.status.replaceAll("_", " ")}</TD>
            </TR>)}</TBody>
          </Table>
          <div className="flex flex-wrap items-center justify-between gap-3 border-t px-4 py-3 text-sm"><div>Page variance: <b>{qty(pageVariance)}</b></div><div className="flex gap-2"><Button variant="outline" disabled={!query.data?.has_previous} onClick={() => setPage(Math.max(1, page - 1))}>Previous</Button><Button variant="outline" disabled={!query.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button></div></div>
        </>}
      </Card>

      <Dialog open={Boolean(requestRow)} onOpenChange={(open) => !open && setRequestRow(null)}>
        <DialogContent>
          <DialogHeader><DialogTitle>Opening Stock Adjustment Request</DialogTitle></DialogHeader>
          <DialogBody className="space-y-4">
            <div className="rounded-md bg-slate-50 p-3 text-sm">{requestRow?.product_code} — <b>{requestRow?.product_name}</b></div>
            <label className="block text-sm">Requested Qty<Input className="mt-1" type="number" step="0.0001" value={requestQty} onChange={(e) => setRequestQty(e.target.value)} /></label>
            <label className="block text-sm">Reason / Notes<textarea className="mt-1 min-h-24 w-full rounded-md border p-2" value={requestNote} onChange={(e) => setRequestNote(e.target.value)} placeholder="Explain shortage/excess against ending stock..." /></label>
          </DialogBody>
          <DialogFooter><Button variant="outline" onClick={() => setRequestRow(null)}>Cancel</Button><Button loading={request.isPending} disabled={!Number(requestQty)} onClick={() => request.mutate()}>Submit Request</Button></DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <Card className="p-4"><div className="text-xs font-medium uppercase tracking-wide text-slate-500">{label}</div><div className="mt-1 text-xl font-semibold tabular-nums">{value}</div></Card>;
}
