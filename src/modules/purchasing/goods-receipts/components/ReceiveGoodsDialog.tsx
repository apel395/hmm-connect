import { useEffect, useState } from "react";
import axios from "axios";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import type { PurchaseOrder } from "@/modules/purchasing/purchase-order/types";
import { useWarehouses } from "@/modules/master/warehouses/hooks/useWarehouses";
import { useReceivablePurchaseOrders, useReceiveGoods, useRemainingPurchaseOrderItems } from "../hooks/useGoodsReceipts";

interface Props { open: boolean; purchaseOrder?: PurchaseOrder | null; onClose: () => void }
interface ReceiveLine {
  purchase_order_item_id: number; product_code?: string; product_name: string; uom?: string;
  ordered_quantity: number; received_quantity: number; remaining_quantity: number; quantity: number;
}
const nowLocal = () => {
  const date = new Date();
  date.setMinutes(date.getMinutes() - date.getTimezoneOffset());
  return date.toISOString().slice(0, 16);
};

export default function ReceiveGoodsDialog({ open, purchaseOrder, onClose }: Props) {
  const { data: warehouses = [] } = useWarehouses();
  const receivable = useReceivablePurchaseOrders(open && !purchaseOrder);
  const [purchaseOrderId, setPurchaseOrderId] = useState<number>();
  const remaining = useRemainingPurchaseOrderItems(purchaseOrderId);
  const receive = useReceiveGoods();
  const [destinationType, setDestinationType] = useState<"WAREHOUSE" | "DIRECT_USE">("WAREHOUSE");
  const [warehouseId, setWarehouseId] = useState<number | null>(null);
  const [receivedAt, setReceivedAt] = useState(nowLocal());
  const [deliveryNote, setDeliveryNote] = useState("");
  const [notes, setNotes] = useState("");
  const [lines, setLines] = useState<ReceiveLine[]>([]);

  useEffect(() => {
    if (!open) return;
    setPurchaseOrderId(purchaseOrder?.id);
    setDestinationType("WAREHOUSE"); setWarehouseId(null); setReceivedAt(nowLocal());
    setDeliveryNote(""); setNotes(""); setLines([]);
  }, [open, purchaseOrder]);
  useEffect(() => {
    setLines((remaining.data ?? []).map((item: any) => ({
      ...item, ordered_quantity: Number(item.ordered_quantity), received_quantity: Number(item.received_quantity),
      remaining_quantity: Number(item.remaining_quantity), quantity: Number(item.remaining_quantity),
    })));
  }, [remaining.data]);

  const updateQuantity = (id: number, value: number) => setLines((current) => current.map((line) => line.purchase_order_item_id === id ? {...line, quantity: Math.min(Math.max(value, 0), line.remaining_quantity)} : line));
  const submit = async () => {
    if (!purchaseOrderId) return alert("Select an approved purchase order.");
    if (destinationType === "WAREHOUSE" && !warehouseId) return alert("Warehouse is required.");
    const items = lines.filter((line) => line.quantity > 0).map((line) => ({purchase_order_item_id: line.purchase_order_item_id, quantity: line.quantity}));
    if (!items.length) return alert("Enter a received quantity greater than zero.");
    try {
      await receive.mutateAsync({purchaseOrderId, payload: {
        received_at: new Date(receivedAt).toISOString(), external_reference: deliveryNote || null,
        destination_type: destinationType, warehouse_id: destinationType === "WAREHOUSE" ? warehouseId : null,
        notes: notes || null, items,
      }});
      onClose();
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      alert(typeof detail === "string" ? detail : "Goods receipt could not be saved");
    }
  };

  return <Dialog open={open} onOpenChange={(value) => !value && onClose()}><DialogContent className="max-w-6xl"><DialogHeader><DialogTitle>Create Receiving</DialogTitle></DialogHeader><DialogBody><div className="space-y-5">
    {!purchaseOrder && <label className="block text-sm font-medium">Approved Purchase Order<select aria-label="Approved Purchase Order" className="mt-1 w-full rounded-md border p-2" value={purchaseOrderId ?? ""} onChange={(event) => setPurchaseOrderId(Number(event.target.value) || undefined)}><option value="">Select approved PO</option>{(receivable.data ?? []).map((order: any) => <option key={order.id} value={order.id}>{order.po_number} — {order.supplier_name}</option>)}</select></label>}
    <div className="grid gap-4 md:grid-cols-2"><label className="text-sm font-medium">Receipt Date<input type="datetime-local" className="mt-1 w-full rounded-md border p-2" value={receivedAt} onChange={(event) => setReceivedAt(event.target.value)}/></label><label className="text-sm font-medium">Delivery Note Number<input className="mt-1 w-full rounded-md border p-2" value={deliveryNote} onChange={(event) => setDeliveryNote(event.target.value)}/></label></div>
    <div><label className="mb-1 block text-sm font-medium">Destination Type</label><select aria-label="Destination Type" className="w-full rounded-md border p-2" value={destinationType} onChange={(event) => setDestinationType(event.target.value as "WAREHOUSE" | "DIRECT_USE")}><option value="WAREHOUSE">Warehouse</option><option value="DIRECT_USE">Direct Use</option></select><p className="mt-1 text-sm text-slate-600">{destinationType === "WAREHOUSE" ? "Accepted quantities will increase warehouse stock." : "Accepted quantities will be recorded but will not increase warehouse stock."}</p></div>
    {destinationType === "WAREHOUSE" && <label className="block text-sm font-medium">Warehouse<select aria-label="Warehouse" className="mt-1 w-full rounded-md border p-2" value={warehouseId ?? ""} onChange={(event) => setWarehouseId(Number(event.target.value) || null)}><option value="">Select warehouse</option>{warehouses.map((warehouse) => <option key={warehouse.id} value={warehouse.id}>{warehouse.code} — {warehouse.name}</option>)}</select></label>}
    {remaining.isLoading ? <p>Loading remaining PO items…</p> : purchaseOrderId && !lines.length ? <p className="rounded border p-4 text-sm text-slate-600">This PO has no remaining items.</p> : !!lines.length && <div className="overflow-x-auto rounded border"><table className="table-grid min-w-[1000px] w-full text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-left">Item Code</th><th className="text-left">Item Name</th><th className="text-right">Ordered</th><th className="text-right">Previously Received</th><th className="text-right">Remaining</th><th className="text-left">UOM</th><th className="p-3 text-right">Received Quantity</th></tr></thead><tbody>{lines.map((line) => <tr key={line.purchase_order_item_id} className="border-t"><td className="p-3">{line.product_code ?? "—"}</td><td>{line.product_name}</td><td className="text-right">{line.ordered_quantity}</td><td className="text-right">{line.received_quantity}</td><td className="text-right">{line.remaining_quantity}</td><td>{line.uom ?? "—"}</td><td className="p-2"><input aria-label={`Received quantity for ${line.product_name}`} type="number" min="0" max={line.remaining_quantity} step="0.01" className="w-full rounded-md border p-2 text-right" value={line.quantity} onChange={(event) => updateQuantity(line.purchase_order_item_id, Number(event.target.value))}/></td></tr>)}</tbody></table></div>}
    <label className="block text-sm font-medium">Notes<textarea className="mt-1 min-h-20 w-full rounded-md border p-2" value={notes} onChange={(event) => setNotes(event.target.value)}/></label>
  </div></DialogBody><DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={receive.isPending || !lines.length} onClick={submit}>{receive.isPending ? "Posting…" : "Create and Post"}</Button></DialogFooter></DialogContent></Dialog>;
}
