import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import type { PurchaseOrder } from "@/modules/purchasing/purchase-order/types";
import { useWarehouses } from "@/modules/master/warehouses/hooks/useWarehouses";
import { useReceivablePurchaseOrders, useReceiveGoods, useRemainingPurchaseOrderItems } from "../hooks/useGoodsReceipts";
import useAuthorization from "@/hooks/useAuthorization";

interface Props { open: boolean; purchaseOrder?: PurchaseOrder | null; onClose: () => void }
interface ReceiveLine {
  purchase_order_item_id: number; product_code?: string; product_name: string; uom?: string;
  ordered_quantity: number; received_quantity: number; remaining_quantity: number; quantity: number;
  unit_cost: number; original_unit_cost: number;
}
const nowLocal = () => {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
};
const money = (value: unknown) => Number(value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function ReceiveGoodsDialog({ open, purchaseOrder, onClose }: Props) {
  const { data: warehouses = [] } = useWarehouses();
  const { isSuperuser, canAccess } = useAuthorization();
  const admin = isSuperuser();
  const canCorrectCost = admin || canAccess(["GENERAL MANAGER", "FINANCE MANAGER", "PURCHASING MANAGER", "PROCUREMENT MANAGER"]);
  const receivable = useReceivablePurchaseOrders(open && !purchaseOrder);
  const [purchaseOrderId, setPurchaseOrderId] = useState<number>();
  const remaining = useRemainingPurchaseOrderItems(purchaseOrderId);
  const receive = useReceiveGoods();
  const [destinationType, setDestinationType] = useState<"WAREHOUSE" | "DIRECT_USE">("WAREHOUSE");
  const [warehouseId, setWarehouseId] = useState<number | null>(null);
  const [receivedAt, setReceivedAt] = useState(nowLocal());
  const [deliveryNote, setDeliveryNote] = useState("");
  const [notes, setNotes] = useState("");
  const [costCorrectionReason, setCostCorrectionReason] = useState("");
  const [lines, setLines] = useState<ReceiveLine[]>([]);

  useEffect(() => {
    if (!open) return;
    setPurchaseOrderId(purchaseOrder?.id);
    setDestinationType("WAREHOUSE"); setWarehouseId(null); setReceivedAt(nowLocal());
    setDeliveryNote(""); setNotes(""); setCostCorrectionReason(""); setLines([]);
  }, [open, purchaseOrder]);
  useEffect(() => {
    setLines((remaining.data ?? []).map((item: any) => ({
      ...item,
      ordered_quantity: Number(item.ordered_quantity), received_quantity: Number(item.received_quantity),
      remaining_quantity: Number(item.remaining_quantity), quantity: Number(item.remaining_quantity),
      unit_cost: Number(item.unit_cost ?? 0), original_unit_cost: Number(item.unit_cost ?? 0),
    })));
  }, [remaining.data]);

  const hasCostOverride = lines.some((line) => Number(line.unit_cost) !== Number(line.original_unit_cost));
  const totalValue = useMemo(() => lines.reduce((sum, line) => sum + Number(line.quantity || 0) * Number(line.unit_cost || 0), 0), [lines]);
  const updateQuantity = (id: number, value: number) => setLines((current) => current.map((line) => line.purchase_order_item_id === id ? {...line, quantity: Math.min(Math.max(value, 0), line.remaining_quantity)} : line));
  const updateCost = (id: number, value: number) => setLines((current) => current.map((line) => line.purchase_order_item_id === id ? {...line, unit_cost: value} : line));
  const submit = async () => {
    if (!purchaseOrderId) return alert("Select an approved purchase order.");
    if (destinationType === "WAREHOUSE" && !warehouseId) return alert("Warehouse is required.");
    const selected = lines.filter((line) => line.quantity > 0);
    if (!selected.length) return alert("Enter a received quantity greater than zero.");
    if (selected.some((line) => Number(line.unit_cost) <= 0)) return alert(canCorrectCost ? "Unit cost must be greater than zero for every received item." : "This PO contains a zero unit cost. Ask an administrator/manager to correct the PO or receiving cost before posting.");
    if (hasCostOverride && !canCorrectCost) return alert("Only an administrator or authorized manager can override PO unit cost.");
    if (hasCostOverride && costCorrectionReason.trim().length < 3) return alert("Enter a correction reason when receiving cost differs from the PO.");
    const items = selected.map((line) => ({purchase_order_item_id: line.purchase_order_item_id, quantity: line.quantity, unit_cost: line.unit_cost}));
    try {
      await receive.mutateAsync({purchaseOrderId, payload: {
        received_at: new Date(receivedAt).toISOString(), external_reference: deliveryNote || null,
        destination_type: destinationType, warehouse_id: destinationType === "WAREHOUSE" ? warehouseId : null,
        notes: notes || null, cost_correction_reason: hasCostOverride ? costCorrectionReason.trim() : null, items,
      }});
      onClose();
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      alert(typeof detail === "string" ? detail : "Goods receipt could not be saved");
    }
  };

  return <Dialog open={open} onOpenChange={(value) => !value && onClose()}><DialogContent className="max-w-6xl"><DialogHeader><DialogTitle>Create Receiving</DialogTitle></DialogHeader><DialogBody><div className="space-y-5">
    {admin && <div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Administrator mode: PO unit cost can be corrected during receiving. Any difference requires a correction reason and is recorded in the receiving audit trail.</div>}
    {!purchaseOrder && <label className="block text-sm font-medium">Approved Purchase Order<select aria-label="Approved Purchase Order" className="mt-1 w-full rounded-md border p-2" value={purchaseOrderId ?? ""} onChange={(event) => setPurchaseOrderId(Number(event.target.value) || undefined)}><option value="">Select approved PO</option>{(receivable.data ?? []).map((order: any) => <option key={order.id} value={order.id}>{order.po_number} — {order.supplier_name}</option>)}</select></label>}
    <div className="grid gap-4 md:grid-cols-2"><label className="text-sm font-medium">Receipt Date<input type="datetime-local" className="mt-1 w-full rounded-md border p-2" value={receivedAt} onChange={(event) => setReceivedAt(event.target.value)}/></label><label className="text-sm font-medium">Delivery Note Number<input className="mt-1 w-full rounded-md border p-2" value={deliveryNote} onChange={(event) => setDeliveryNote(event.target.value)}/></label></div>
    <div><label className="mb-1 block text-sm font-medium">Destination Type</label><select aria-label="Destination Type" className="w-full rounded-md border p-2" value={destinationType} onChange={(event) => setDestinationType(event.target.value as "WAREHOUSE" | "DIRECT_USE")}><option value="WAREHOUSE">Warehouse</option><option value="DIRECT_USE">Direct Use</option></select><p className="mt-1 text-sm text-slate-600">{destinationType === "WAREHOUSE" ? "Accepted quantities will increase warehouse stock." : "Accepted quantities will be recorded but will not increase warehouse stock."}</p></div>
    {destinationType === "WAREHOUSE" && <label className="block text-sm font-medium">Warehouse<select aria-label="Warehouse" className="mt-1 w-full rounded-md border p-2" value={warehouseId ?? ""} onChange={(event) => setWarehouseId(Number(event.target.value) || null)}><option value="">Select warehouse</option>{warehouses.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.code} — {warehouse.name}</option>)}</select></label>}
    {remaining.isLoading ? <p>Loading remaining PO items…</p> : purchaseOrderId && !lines.length ? <p className="rounded border p-4 text-sm text-slate-600">This PO has no remaining items.</p> : !!lines.length && <div className="overflow-x-auto rounded border"><table className="table-grid min-w-[1220px] w-full table-fixed text-sm"><thead className="bg-slate-50"><tr><th className="w-28 p-3 text-left">Item Code</th><th className="w-56 text-left">Item Name</th><th className="w-24 text-right">Ordered</th><th className="w-32 text-right">Previously Received</th><th className="w-24 text-right">Remaining</th><th className="w-24 text-left">UOM</th><th className="w-40 text-right">Received Qty</th><th className="w-48 text-right">Unit Cost</th><th className="w-48 p-3 text-right">Amount</th></tr></thead><tbody>{lines.map((line) => <tr key={line.purchase_order_item_id} className="border-t"><td className="p-3">{line.product_code ?? "—"}</td><td>{line.product_name}</td><td className="text-right tabular-nums">{line.ordered_quantity}</td><td className="text-right tabular-nums">{line.received_quantity}</td><td className="text-right tabular-nums">{line.remaining_quantity}</td><td>{line.uom ?? "—"}</td><td className="w-40 p-2"><input aria-label={`Received quantity for ${line.product_name}`} type="number" min="0" max={line.remaining_quantity} step="0.01" className="w-full min-w-0 rounded-md border p-2 text-right tabular-nums" value={line.quantity} onChange={(event) => updateQuantity(line.purchase_order_item_id, Number(event.target.value))}/></td><td className="w-48 p-2">{canCorrectCost ? <div className="w-full min-w-0"><CurrencyInput value={line.unit_cost} onValueChange={(value) => updateCost(line.purchase_order_item_id, value)} /></div> : <div className={`w-full rounded-md border bg-slate-50 p-2 text-right tabular-nums ${line.unit_cost <= 0 ? "border-red-300 text-red-700" : ""}`}>{money(line.unit_cost)}</div>}</td><td className="w-48 p-3 text-right font-medium tabular-nums">{money(line.quantity * line.unit_cost)}</td></tr>)}</tbody><tfoot><tr><td colSpan={8} className="p-3 text-right font-semibold">Total Cost</td><td className="p-3 text-right text-base font-bold tabular-nums">{money(totalValue)}</td></tr></tfoot></table></div>}
    {canCorrectCost && hasCostOverride && <label className="block text-sm font-medium">Cost Correction Reason *<textarea className="mt-1 min-h-20 w-full rounded-md border border-amber-300 bg-amber-50 p-2" value={costCorrectionReason} onChange={(event) => setCostCorrectionReason(event.target.value)} placeholder="Explain why the receiving cost differs from the approved PO."/></label>}
    <label className="block text-sm font-medium">Notes<textarea className="mt-1 min-h-20 w-full rounded-md border p-2" value={notes} onChange={(event) => setNotes(event.target.value)}/></label>
  </div></DialogBody><DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={receive.isPending || !lines.length} onClick={submit}>{receive.isPending ? "Posting…" : "Create and Post"}</Button></DialogFooter></DialogContent></Dialog>;
}
