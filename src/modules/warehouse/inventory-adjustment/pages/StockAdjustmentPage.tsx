import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {Plus, Trash2, Eye, Pencil, PlayCircle, Ban, Boxes, Printer} from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Pagination from "@/components/datatable/Pagination";
import Dialog from "@/components/ui/Dialog";
import { DialogContent, DialogHeader, DialogTitle, DialogBody, DialogFooter } from "@/components/ui/Dialog";
import SearchableSelect from "@/components/form/SearchableSelect";
import useAuthStore from "@/store/auth";
import { canAccess } from "@/lib/access";
import { stockAdjustmentApi, type StockAdjustmentItemIn } from "../api";
import { inventoryApi } from "@/modules/warehouse/inventory/api";
import { warehouseApi } from "@/modules/master/warehouses/api/warehouseApi";

const INVENTORY_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "PURCHASING", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];
const money = (v: unknown) => "Rp " + Number(v ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const num = (v: unknown) => Number(v ?? 0).toLocaleString("id-ID");
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const PAGE_SIZE = 25;

interface Line {
  key: number;
  product_id?: number;
  product_code?: string;
  product_name?: string;
  uom?: string;
  system_quantity: number;
  adjusted_quantity: number;
  unit_cost: number;
  reason: string;
}

const statusVariant: Record<string, "default" | "warning" | "success" | "outline"> = {
  DRAFT: "warning",
  POSTED: "success",
  VOID: "outline",
};

function fmtDate(value: unknown): string {
  if (!value) return "-";
  const d = new Date(String(value));
  if (isNaN(d.getTime())) return String(value);
  return d.toLocaleDateString("id-ID");
}

export default function StockAdjustmentPage() {
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const canAdjust = canAccess(user, INVENTORY_ROLES, "inventory.adjust");

  const [status, setStatus] = useState("ALL");
  const [warehouseFilter, setWarehouseFilter] = useState<string>("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const listQuery = useQuery({
    queryKey: ["stock-adjustments", { status, warehouseFilter, search, page }],
    queryFn: async () => (await stockAdjustmentApi.list({
      page,
      page_size: PAGE_SIZE,
      status: status === "ALL" ? undefined : status,
      warehouse_id: warehouseFilter ? Number(warehouseFilter) : undefined,
      search: search.trim() || undefined,
    })).data,
  });
  const data: any = listQuery.data ?? {};
  const rows: any[] = data.items ?? [];
  const summary = data.summary ?? {};
  const statusCounts: Record<string, number> = summary.status_counts ?? {};
  const pages = Math.max(data.total_pages ?? 0, 1);

  useEffect(() => setPage(1), [status, warehouseFilter, search]);

  const warehousesQuery = useQuery({
    queryKey: ["stock-adjustments-warehouses"],
    queryFn: async () => (await warehouseApi.list()).data,
  });
  const warehouses: any[] = warehousesQuery.data ?? [];
  const warehouseOptions = warehouses.map((w) => ({ id: w.id, code: w.code, name: w.name }));

  const [dialogOpen, setDialogOpen] = useState(false);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [editing, setEditing] = useState<any | null>(null);
  const [warehouseId, setWarehouseId] = useState<number | undefined>(undefined);
  const [adjustmentDate, setAdjustmentDate] = useState("");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<Line[]>([]);
  const [formError, setFormError] = useState("");
  const [saving, setSaving] = useState(false);
  const [lineSeq, setLineSeq] = useState(1);

  const inventoryQuery = useQuery({
    queryKey: ["stock-adjustment-inventory", warehouseId],
    queryFn: async () => (await inventoryApi.list({ page: 1, page_size: 100, warehouse_id: warehouseId })).data,
    enabled: Boolean(warehouseId),
  });
  const invRows: any[] = inventoryQuery.data?.items ?? [];
  const productOptions = invRows.map((row) => ({
    id: row.product_id,
    label: `${row.product_code} - ${row.product_name} (${num(row.quantity)} ${row.uom})`,
    keywords: [row.product_code, row.product_name, row.warehouse_name],
  }));
  const invByProduct = useMemo(() => {
    const items: any[] = inventoryQuery.data?.items ?? [];
    return Object.fromEntries(items.map((row) => [row.product_id, row]));
  }, [inventoryQuery.data]);

  const openCreate = () => {
    setEditing(null);
    setWarehouseId(undefined);
    setAdjustmentDate(new Date().toISOString().slice(0, 10));
    setReason("");
    setNotes("");
    setLines([]);
    setFormError("");
    setDialogOpen(true);
  };

  const openEdit = (row: any) => {
    setEditing(row);
    setWarehouseId(row.warehouse_id);
    setAdjustmentDate(String(row.adjustment_date ?? "").slice(0, 10));
    setReason(row.reason ?? "");
    setNotes(row.notes ?? "");
    setLines((row.items ?? []).map((item: any) => {
      const seq = lineSeq + Math.floor(Math.random() * 100000);
      return {
        key: seq,
        product_id: item.product_id,
        product_code: item.product_code,
        product_name: item.product_name,
        uom: item.uom,
        system_quantity: Number(item.system_quantity ?? 0),
        adjusted_quantity: Number(item.adjusted_quantity ?? 0),
        unit_cost: Number(item.unit_cost ?? 0),
        reason: item.reason ?? "",
      };
    }));
    setLineSeq((value) => value + 100000);
    setFormError("");
    setDialogOpen(true);
  };

  const addLine = () => {
    setLines((current) => {
      const next = [...current, { key: lineSeq, system_quantity: 0, adjusted_quantity: 0, unit_cost: 0, reason: "" }];
      setLineSeq((value) => value + 1);
      return next;
    });
  };

  const updateLine = (key: number, patch: Partial<Line>) => {
    setLines((current) => current.map((line) => (line.key === key ? { ...line, ...patch } : line)));
  };

  const removeLine = (key: number) => {
    setLines((current) => current.filter((line) => line.key !== key));
  };

  const selectProduct = (line: Line, productId?: number) => {
    if (!productId) {
      updateLine(line.key, { product_id: undefined });
      return;
    }
    const inventory = invByProduct[productId];
    const system = Number(inventory?.quantity ?? 0);
    updateLine(line.key, {
      product_id: productId,
      product_code: inventory?.product_code,
      product_name: inventory?.product_name,
      uom: inventory?.uom,
      system_quantity: system,
      adjusted_quantity: system,
      unit_cost: Number(inventory?.average_cost ?? 0),
    });
  };

  const validateForm = (): string => {
    if (!canAdjust) return "You do not have permission to create adjustments";
    if (!warehouseId) return "Warehouse is required";
    if (!reason.trim()) return "Reason is required";
    const valid = lines.filter((line) => line.product_id && Number.isFinite(line.adjusted_quantity));
    if (valid.length === 0) return "Add at least one item line";
    if (!valid.some((line) => Math.abs(Number(line.adjusted_quantity) - Number(line.system_quantity)) > 0.0001)) {
      return "At least one line must change the current quantity";
    }
    return "";
  };

  const buildItems = (): StockAdjustmentItemIn[] =>
    lines
      .filter((line) => line.product_id && Number.isFinite(line.adjusted_quantity))
      .map((line) => ({ product_id: line.product_id!, adjusted_quantity: Number(line.adjusted_quantity), reason: line.reason.trim() || null }));

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (editing) {
        return (await stockAdjustmentApi.update(editing.id, {
          adjustment_date: adjustmentDate || null,
          reason,
          notes: notes || null,
          items: buildItems(),
        })).data;
      }
      return (await stockAdjustmentApi.create({
        warehouse_id: warehouseId!,
        adjustment_date: adjustmentDate || null,
        reason,
        notes: notes || null,
        items: buildItems(),
      })).data;
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["stock-adjustments"] });
      setDialogOpen(false);
      setSaving(false);
    },
    onError: (error: any) => {
      setSaving(false);
      setFormError(error?.response?.data?.detail?.message || error?.response?.data?.detail || error?.message || "Save failed");
    },
  });

  const handleSave = () => {
    const error = validateForm();
    if (error) {
      setFormError(error);
      return;
    }
    setFormError("");
    setSaving(true);
    saveMutation.mutate();
  };

  const postMutation = useMutation({
    mutationFn: async (id: number) => (await stockAdjustmentApi.post(id)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["stock-adjustments"] }),
    onError: (error: any) => setFormError(typeof error?.response?.data?.detail === "string" ? error.response.data.detail : error?.message || "Post failed"),
  });

  const voidMutation = useMutation({
    mutationFn: async (id: number) => (await stockAdjustmentApi.void(id)).data,
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["stock-adjustments"] }),
    onError: (error: any) => setFormError(typeof error?.response?.data?.detail === "string" ? error.response.data.detail : error?.message || "Void failed"),
  });

  const detailQuery = useQuery({
    queryKey: ["stock-adjustment-detail", detailId],
    queryFn: async () => detailId ? (await stockAdjustmentApi.detail(detailId)).data : null,
    enabled: detailId !== null,
  });
  const detail: any = detailQuery.data;

  const totalLines = lines.length;
  const totalDeltaLines = lines.filter((line) => Math.abs(line.adjusted_quantity - line.system_quantity) > 0.0001).length;

  return (
    <div className="space-y-6">
      <PageHeader  actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} title="Stock Adjustment" description="Correct warehouse stock for damage, expiry, found surplus or bookkeeping errors. Adjustments are posted to inventory and recorded as stock movements." />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Adjustments</div><div className="mt-2 text-2xl font-bold">{num(data.total_items ?? 0)}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Draft</div><div className="mt-2 text-2xl font-bold">{num(statusCounts.DRAFT ?? 0)}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Posted</div><div className="mt-2 text-2xl font-bold text-emerald-700">{num(statusCounts.POSTED ?? 0)}</div></Card>
        <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Voided</div><div className="mt-2 text-2xl font-bold text-slate-500">{num(statusCounts.VOID ?? 0)}</div></Card>
      </div>

      <Card className="p-4">
        <div className="grid gap-3 md:grid-cols-[1fr_200px_220px_auto]">
          <input className={input} placeholder="Search number, reason or warehouse" value={search} onChange={(e) => setSearch(e.target.value)} />
          <select className={input} value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="ALL">All statuses</option>
            <option value="DRAFT">Draft</option>
            <option value="POSTED">Posted</option>
            <option value="VOID">Void</option>
          </select>
          <select className={input} value={warehouseFilter} onChange={(e) => setWarehouseFilter(e.target.value)}>
            <option value="">All warehouses</option>
            {warehouses.map((w) => <option key={w.id} value={w.id}>{w.code} - {w.name}</option>)}
          </select>
          <Button variant="primary" onClick={openCreate} disabled={!canAdjust}><Plus className="h-4 w-4" />New Adjustment</Button>
        </div>
        {!canAdjust && <div className="mt-2 text-xs text-slate-500">You can view adjustments. Only warehouse staff with adjustment permission can create or post them.</div>}
      </Card>

      <Card className="p-0">
        {listQuery.isLoading ? <Loading /> : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead><tr className="whitespace-nowrap border-b text-xs uppercase tracking-wide text-slate-500">
                  <th className="px-4 py-3">Number</th><th className="px-4 py-3">Date</th><th className="px-4 py-3">Warehouse</th><th className="px-4 py-3">Reason</th>
                  <th className="px-4 py-3">Status</th><th className="px-4 py-3 text-right">Value</th><th className="px-4 py-3">Created By</th><th className="px-4 py-3 text-right">Actions</th>
                </tr></thead>
                <tbody>
                  {rows.length === 0 && <tr><td colSpan={8} className="px-4 py-10 text-center text-slate-500">No stock adjustments match the current filters.</td></tr>}
                  {rows.map((row) => (
                    <tr key={row.id} className="border-t">
                      <td className="px-4 py-3 font-medium text-emerald-700">{row.adjustment_number}</td>
                      <td className="px-4 py-3 whitespace-nowrap">{fmtDate(row.adjustment_date)}</td>
                      <td className="px-4 py-3">{row.warehouse_code} - {row.warehouse_name}</td>
                      <td className="px-4 py-3"><span className="block max-w-[260px] truncate" title={row.reason}>{row.reason}</span></td>
                      <td className="px-4 py-3"><Badge variant={statusVariant[row.status] ?? "default"}>{row.status}</Badge></td>
                      <td className="px-4 py-3 text-right font-semibold">{money(row.total_adjustment_value)}</td>
                      <td className="px-4 py-3">{row.created_by_name || "-"}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center justify-end gap-1">
                          <Button variant="ghost" size="xs" onClick={() => setDetailId(row.id)}><Eye className="h-4 w-4" /></Button>
                          {canAdjust && row.status === "DRAFT" && (
                            <>
                              <Button variant="ghost" size="xs" onClick={() => openEdit(row)}><Pencil className="h-4 w-4" /></Button>
                              <Button variant="success" size="xs" disabled={postMutation.isPending} onClick={() => postMutation.mutate(row.id)}><PlayCircle className="h-4 w-4" />Post</Button>
                              <Button variant="ghost" size="xs" disabled={voidMutation.isPending} onClick={() => voidMutation.mutate(row.id)}><Ban className="h-4 w-4" />Void</Button>
                            </>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="p-4"><Pagination page={page} pages={pages} total={data.total_items ?? 0} pageSize={PAGE_SIZE} noun="adjustments" onChange={setPage} /></div>
          </>
        )}
      </Card>

      <Dialog open={dialogOpen} onOpenChange={(open: boolean) => { if (!saving) setDialogOpen(open); setFormError(""); }}>
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2"><Boxes className="h-5 w-5 text-[#0F6758]" />{editing ? `Edit ${editing.adjustment_number}` : "New Stock Adjustment"}</DialogTitle>
          </DialogHeader>
          <DialogBody>
            <form id="adjustment-form">
              <div className="grid gap-3 md:grid-cols-[1fr_180px]">
                <SearchableSelect label="Warehouse" required value={warehouseId} options={warehouseOptions} disabled={Boolean(editing)} placeholder="Select warehouse" onChange={(value) => setWarehouseId(value)} />
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-slate-500">Adjustment Date</span>
                  <input type="date" className={input} value={adjustmentDate} onChange={(e) => setAdjustmentDate(e.target.value)} />
                </label>
              </div>
              <div className="mt-3">
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-slate-500">Reason <span className="text-red-500">*</span></span>
                  <input className={input} placeholder="e.g. Damaged goods, expired items, found surplus, stock count variance" value={reason} onChange={(e) => setReason(e.target.value)} />
                </label>
              </div>
              <div className="mt-3">
                <label className="block">
                  <span className="mb-1 block text-xs font-medium text-slate-500">Notes</span>
                  <textarea className="h-20 w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm" value={notes} onChange={(e) => setNotes(e.target.value)} />
                </label>
              </div>

              <div className="mt-4">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-xs font-semibold uppercase tracking-wide text-slate-500">Item Lines ({totalLines}, {totalDeltaLines} changed)</span>
                  <button type="button" onClick={addLine} className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-emerald-700 hover:bg-emerald-50"><Plus className="h-3.5 w-3.5" />Add item</button>
                </div>
                {!warehouseId && <div className="rounded-md border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500">Select a warehouse to load stock items and unit costs.</div>}
                {warehouseId && lines.length === 0 && <div className="rounded-md border border-dashed border-slate-300 p-6 text-center text-xs text-slate-500">Add a product line to adjust. The new quantity replaces the current on-hand quantity.</div>}
                {lines.map((line) => {
                  const delta = Number(line.adjusted_quantity) - Number(line.system_quantity);
                  return (
                    <div key={line.key} className="mb-2 rounded-md border border-slate-200 p-2">
                      <div className="grid gap-2 md:grid-cols-[1fr_120px_100px_130px_32px]">
                        <SearchableSelect label="Product" value={line.product_id} options={productOptions} placeholder="Search product to adjust" onChange={(value) => selectProduct(line, value)} />
                        <label className="block">
                          <span className="mb-1 block text-xs font-medium text-slate-500">On Hand</span>
                          <div className="flex h-10 items-center rounded-md border border-slate-200 bg-slate-50 px-3 text-sm text-slate-700">{num(line.system_quantity)} {line.uom ?? ""}</div>
                        </label>
                        <label className="block">
                          <span className="mb-1 block text-xs font-medium text-slate-500">New Qty</span>
                          <input type="number" min={0} step="0.01" className={input} value={line.adjusted_quantity} onChange={(e) => updateLine(line.key, { adjusted_quantity: Number(e.target.value) })} />
                        </label>
                        <label className="block">
                          <span className="mb-1 block text-xs font-medium text-slate-500">Change</span>
                          <div className={`flex h-10 items-center rounded-md border px-3 text-sm font-semibold ${delta > 0 ? "border-emerald-200 bg-emerald-50 text-emerald-700" : delta < 0 ? "border-red-200 bg-red-50 text-red-700" : "border-slate-200 bg-slate-50 text-slate-500"}`}>
                            {delta > 0 ? "+" : ""}{num(delta)}
                          </div>
                        </label>
                        <button type="button" onClick={() => removeLine(line.key)} className="mt-6 grid h-10 w-8 place-items-center rounded-md text-slate-400 hover:bg-red-50 hover:text-red-600"><Trash2 className="h-4 w-4" /></button>
                      </div>
                      <input className="mt-2 h-8 w-full rounded-md border border-slate-200 px-2 text-xs" placeholder="Line-specific reason (optional, defaults to document reason)" value={line.reason} onChange={(e) => updateLine(line.key, { reason: e.target.value })} />
                      {line.product_id && (
                        <div className="mt-1 flex items-center gap-2 text-[11px] text-slate-500">
                          <span>Avg cost: {money(line.unit_cost)}</span>
                          <span>Line value: {money(Math.abs(delta) * Number(line.unit_cost ?? 0))}</span>
                          {Number(line.system_quantity) === 0 && <span className="text-red-600">No current stock</span>}
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
              {formError && <div className="mt-4 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{formError}</div>}
              {inventoryQuery.isLoading && warehouseId && <div className="mt-2 text-xs text-slate-400">Loading stock items...</div>}
            </form>
          </DialogBody>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)} disabled={saving}>Cancel</Button>
            <Button variant="success" onClick={handleSave} loading={saving}>{editing ? "Save Changes" : "Create Adjustment"}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={detailId !== null} onOpenChange={(open: boolean) => { if (!open) setDetailId(null); }}>
        <DialogContent>
          <DialogHeader><DialogTitle className="flex items-center gap-2"><Eye className="h-5 w-5 text-[#0F6758]" />{detail?.adjustment_number ?? "Stock Adjustment"}</DialogTitle></DialogHeader>
          <DialogBody>
            {detailQuery.isLoading || !detail ? <Loading /> : (
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div><div className="text-xs uppercase tracking-wide text-slate-500">Status</div><Badge variant={statusVariant[detail.status] ?? "default"}>{detail.status}</Badge></div>
                  <div><div className="text-xs uppercase tracking-wide text-slate-500">Date</div>{fmtDate(detail.adjustment_date)}</div>
                  <div><div className="text-xs uppercase tracking-wide text-slate-500">Warehouse</div>{detail.warehouse_code} - {detail.warehouse_name}</div>
                  <div><div className="text-xs uppercase tracking-wide text-slate-500">Total Value</div><span className="font-semibold">{money(detail.total_adjustment_value)}</span></div>
                  <div className="col-span-2"><div className="text-xs uppercase tracking-wide text-slate-500">Reason</div>{detail.reason}</div>
                  {detail.notes && <div className="col-span-2"><div className="text-xs uppercase tracking-wide text-slate-500">Notes</div>{detail.notes}</div>}
                  <div><div className="text-xs uppercase tracking-wide text-slate-500">Created By</div>{detail.created_by_name || "-"}</div>
                  {detail.posted_by_name && <div><div className="text-xs uppercase tracking-wide text-slate-500">Posted By</div>{detail.posted_by_name}</div>}
                </div>
                <table className="w-full text-left text-sm">
                  <thead><tr className="border-b text-xs uppercase tracking-wide text-slate-500">
                    <th className="px-2 py-2">Product</th><th className="px-2 py-2 text-right">On Hand</th><th className="px-2 py-2 text-right">New Qty</th><th className="px-2 py-2 text-right">Δ</th><th className="px-2 py-2 text-right">Value</th>
                  </tr></thead>
                  <tbody>
                    {(detail.items ?? []).map((item: any) => (
                      <tr key={item.id} className="border-t">
                        <td className="px-2 py-2"><span className="font-medium">{item.product_name}</span> <span className="text-slate-400">({item.product_code})</span></td>
                        <td className="px-2 py-2 text-right tabular-nums">{num(item.system_quantity)} {item.uom}</td>
                        <td className="px-2 py-2 text-right tabular-nums">{num(item.adjusted_quantity)}</td>
                        <td className={`px-2 py-2 text-right tabular-nums font-semibold ${Number(item.delta_quantity) > 0 ? "text-emerald-700" : Number(item.delta_quantity) < 0 ? "text-red-700" : ""}`}>{Number(item.delta_quantity) > 0 ? "+" : ""}{num(item.delta_quantity)}</td>
                        <td className="px-2 py-2 text-right tabular-nums">{money(item.line_value)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {(postMutation.isError || voidMutation.isError) && formError && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{formError}</div>}
              </div>
            )}
          </DialogBody>
          <DialogFooter>
            {canAdjust && detail ? (
              <>
                {detail.status === "DRAFT" && <Button variant="outline" onClick={() => { setDetailId(null); openEdit(detail); }}>Edit</Button>}
                {detail.status === "DRAFT" && <Button variant="success" onClick={() => postMutation.mutate(detail.id)} disabled={postMutation.isPending}><PlayCircle className="h-4 w-4" />Post</Button>}
                <Button variant="outline" onClick={() => setDetailId(null)}>Close</Button>
              </>
            ) : <Button variant="outline" onClick={() => setDetailId(null)}>Close</Button>}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}