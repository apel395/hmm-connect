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
  unit_cost: number; original_unit_cost: number; is_taxable?: boolean; tax_rate?: number;
}
const nowLocal = () => { const date = new Date(); date.setMinutes(date.getMinutes() - date.getTimezoneOffset()); return date.toISOString().slice(0, 16); };
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

  useEffect(() => { if (!open) return; setPurchaseOrderId(purchaseOrder?.id); setDestinationType("WAREHOUSE"); setWarehouseId(null); setReceivedAt(nowLocal()); setDeliveryNote(""); setNotes(""); setCostCorrectionReason(""); setLines([]); }, [open, purchaseOrder]);
  useEffect(() => { setLines((remaining.data ?? []).map((item: any) => ({ ...item, ordered_quantity:Number(item.ordered_quantity), received_quantity:Number(item.received_quantity), remaining_quantity:Number(item.remaining_quantity), quantity:Number(item.remaining_quantity), unit_cost:Number(item.unit_cost ?? 0), original_unit_cost:Number(item.unit_cost ?? 0), is_taxable:Boolean(item.is_taxable), tax_rate:Number(item.tax_rate ?? 0) }))); }, [remaining.data]);

  const hasCostOverride = lines.some((line) => Number(line.unit_cost) !== Number(line.original_unit_cost));
  const subtotal = useMemo(() => lines.reduce((sum,line)=>sum+Number(line.quantity||0)*Number(line.unit_cost||0),0),[lines]);
  const taxAmount = useMemo(() => lines.reduce((sum,line)=>sum+(line.is_taxable ? Number(line.quantity||0)*Number(line.unit_cost||0)*Number(line.tax_rate||0)/100 : 0),0),[lines]);
  const grandTotal = subtotal + taxAmount;
  const updateQuantity = (id:number,value:number)=>setLines((current)=>current.map((line)=>line.purchase_order_item_id===id?{...line,quantity:Math.min(Math.max(value,0),line.remaining_quantity)}:line));
  const updateCost = (id:number,value:number)=>setLines((current)=>current.map((line)=>line.purchase_order_item_id===id?{...line,unit_cost:value}:line));
  const submit = async () => {
    if (!purchaseOrderId) return alert("Select an approved purchase order.");
    if (destinationType === "WAREHOUSE" && !warehouseId) return alert("Warehouse is required.");
    const selected = lines.filter((line) => line.quantity > 0);
    if (!selected.length) return alert("Enter a received quantity greater than zero.");
    if (selected.some((line) => Number(line.unit_cost) <= 0)) return alert(canCorrectCost ? "Unit cost must be greater than zero for every received item." : "This PO contains a zero unit cost. Ask an administrator/manager to correct the PO or receiving cost before approval.");
    if (hasCostOverride && !canCorrectCost) return alert("Only an administrator or authorized manager can override PO unit cost.");
    if (hasCostOverride && costCorrectionReason.trim().length < 3) return alert("Enter a correction reason when receiving cost differs from the PO.");
    try {
      await receive.mutateAsync({purchaseOrderId,payload:{received_at:new Date(receivedAt).toISOString(),external_reference:deliveryNote||null,destination_type:destinationType,warehouse_id:destinationType==="WAREHOUSE"?warehouseId:null,notes:notes||null,cost_correction_reason:hasCostOverride?costCorrectionReason.trim():null,items:selected.map((line)=>({purchase_order_item_id:line.purchase_order_item_id,quantity:line.quantity,unit_cost:line.unit_cost}))}});
      onClose();
    } catch (error) { const detail=axios.isAxiosError(error)?error.response?.data?.detail:null; alert(typeof detail==="string"?detail:"Goods receipt could not be saved"); }
  };

  return <Dialog open={open} onOpenChange={(value)=>!value&&onClose()}><DialogContent className="max-w-7xl"><DialogHeader><DialogTitle>Create Receiving Report</DialogTitle></DialogHeader><DialogBody><div className="space-y-5">
    <div className="rounded border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900">Receiving is saved as <strong>DRAFT</strong>. It must follow Store → Chef → PM/Camp Boss → HO Purchasing → Finance → General Manager approval before stock can be posted.</div>
    {admin&&<div className="rounded border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">Administrator testing access remains available for approval stages and authorized cost correction.</div>}
    {!purchaseOrder&&<label className="block text-sm font-medium">Approved Purchase Order<select aria-label="Approved Purchase Order" className="mt-1 w-full rounded-md border p-2" value={purchaseOrderId??""} onChange={(event)=>setPurchaseOrderId(Number(event.target.value)||undefined)}><option value="">Select approved PO</option>{(receivable.data??[]).map((order:any)=><option key={order.id} value={order.id}>{order.po_number} — {order.supplier_name}</option>)}</select></label>}
    <div className="grid gap-4 md:grid-cols-2"><label className="text-sm font-medium">Receipt Date<input type="datetime-local" className="mt-1 w-full rounded-md border p-2" value={receivedAt} onChange={(e)=>setReceivedAt(e.target.value)}/></label><label className="text-sm font-medium">Delivery Note Number<input className="mt-1 w-full rounded-md border p-2" value={deliveryNote} onChange={(e)=>setDeliveryNote(e.target.value)}/></label></div>
    <div><label className="mb-1 block text-sm font-medium">Destination Type</label><select aria-label="Destination Type" className="w-full rounded-md border p-2" value={destinationType} onChange={(e)=>setDestinationType(e.target.value as "WAREHOUSE"|"DIRECT_USE")}><option value="WAREHOUSE">Warehouse</option><option value="DIRECT_USE">Direct Use</option></select></div>
    {destinationType==="WAREHOUSE"&&<label className="block text-sm font-medium">Warehouse<select aria-label="Warehouse" className="mt-1 w-full rounded-md border p-2" value={warehouseId??""} onChange={(e)=>setWarehouseId(Number(e.target.value)||null)}><option value="">Select warehouse</option>{warehouses.map((warehouse)=><option key={warehouse.id} value={warehouse.id}>{warehouse.code} — {warehouse.name}</option>)}</select></label>}
    {remaining.isLoading?<p>Loading remaining PO items…</p>:purchaseOrderId&&!lines.length?<p className="rounded border p-4 text-sm text-slate-600">This PO has no remaining items.</p>:!!lines.length&&<div className="overflow-x-auto rounded border"><table className="table-grid min-w-[1450px] w-full text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-left">Item</th><th className="text-right">Ordered</th><th className="text-right">Received</th><th className="text-right">Remaining</th><th>UOM</th><th className="text-right">Receive Qty</th><th className="text-right">Unit Cost</th><th>PPN</th><th className="text-right">Subtotal</th><th className="text-right">PPN Amount</th><th className="p-3 text-right">Total</th></tr></thead><tbody>{lines.map((line)=>{const lineSub=line.quantity*line.unit_cost;const tax=line.is_taxable?lineSub*Number(line.tax_rate||0)/100:0;return <tr key={line.purchase_order_item_id} className="border-t"><td className="p-3"><div className="font-medium">{line.product_name}</div><div className="text-xs text-slate-500">{line.product_code??"—"}</div></td><td className="text-right">{line.ordered_quantity}</td><td className="text-right">{line.received_quantity}</td><td className="text-right font-medium">{line.remaining_quantity}</td><td>{line.uom??"—"}</td><td className="p-2"><input aria-label={`Received quantity for ${line.product_name}`} type="number" min="0" max={line.remaining_quantity} step="0.01" className="w-32 rounded-md border p-2 text-right" value={line.quantity} onChange={(e)=>updateQuantity(line.purchase_order_item_id,Number(e.target.value))}/></td><td className="p-2">{canCorrectCost?<div className="w-44"><CurrencyInput value={line.unit_cost} onValueChange={(value)=>updateCost(line.purchase_order_item_id,value)}/></div>:<div className="text-right">{money(line.unit_cost)}</div>}</td><td>{line.is_taxable?`${Number(line.tax_rate||0)}%`:"Non-PPN"}</td><td className="text-right">{money(lineSub)}</td><td className="text-right">{money(tax)}</td><td className="p-3 text-right font-semibold">{money(lineSub+tax)}</td></tr>})}</tbody></table></div>}
    <div className="ml-auto grid max-w-md gap-2 rounded-lg border bg-slate-50 p-4 text-sm"><div className="flex justify-between"><span>Subtotal</span><strong>{money(subtotal)}</strong></div><div className="flex justify-between"><span>PPN</span><strong>{money(taxAmount)}</strong></div><div className="flex justify-between border-t pt-2 text-base"><span>Grand Total</span><strong>{money(grandTotal)}</strong></div></div>
    {canCorrectCost&&hasCostOverride&&<label className="block text-sm font-medium">Cost Correction Reason *<textarea className="mt-1 min-h-20 w-full rounded-md border border-amber-300 bg-amber-50 p-2" value={costCorrectionReason} onChange={(e)=>setCostCorrectionReason(e.target.value)}/></label>}
    <label className="block text-sm font-medium">Notes<textarea className="mt-1 min-h-20 w-full rounded-md border p-2" value={notes} onChange={(e)=>setNotes(e.target.value)}/></label>
  </div></DialogBody><DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={receive.isPending||!lines.length} onClick={submit}>{receive.isPending?"Saving…":"Save Receiving Draft"}</Button></DialogFooter></DialogContent></Dialog>;
}
