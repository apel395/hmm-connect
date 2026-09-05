import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { useQuery } from "@tanstack/react-query";
import CurrencyInput from "@/components/form/CurrencyInput";
import SearchableSelect from "@/components/form/SearchableSelect";
import Button from "@/components/ui/Button";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import useAuthorization from "@/hooks/useAuthorization";
import {
  filterBusinessUnits,
  listDepartments,
  listLocations,
} from "@/modules/admin/organization/api";
import { useWarehouses } from "@/modules/master/warehouses/hooks/useWarehouses";
import type { PurchaseOrder } from "@/modules/purchasing/purchase-order/types";
import { isBeforeNow, nowLocal } from "@/utils/dateConstraints";
import {
  useReceivablePurchaseOrders,
  useReceiveGoods,
  useRemainingPurchaseOrderItems,
} from "../hooks/useGoodsReceipts";

interface Props {
  open: boolean;
  purchaseOrder?: PurchaseOrder | null;
  onClose: () => void;
}
interface ReceiveLine {
  purchase_order_item_id: number;
  product_code?: string;
  product_name: string;
  uom?: string;
  ordered_quantity: number;
  received_quantity: number;
  remaining_quantity: number;
  quantity: number;
  unit_cost: number;
  original_unit_cost: number;
  is_taxable?: boolean;
  tax_rate?: number;
}
const money = (value: unknown) => Number(value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function ReceiveGoodsDialog({ open, purchaseOrder, onClose }: Props) {
  const { data: warehouses = [] } = useWarehouses();
  const { isSuperuser, canAccess, canBackdate } = useAuthorization();
  const canCorrectCost = isSuperuser() || canAccess(["GENERAL MANAGER", "FINANCE MANAGER", "PURCHASING MANAGER", "PROCUREMENT MANAGER"]);
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
  const selectedPO: any = purchaseOrder ?? (receivable.data ?? []).find((order: any) => order.id === purchaseOrderId);
  const businessUnits = useQuery({ queryKey: ["business-units", "receiving-dimensions"], queryFn: () => filterBusinessUnits({ is_active: true }), enabled: open && Boolean(selectedPO?.business_unit_id) && !selectedPO?.business_unit_name });
  const departments = useQuery({ queryKey: ["departments", "receiving-dimensions", selectedPO?.business_unit_id], queryFn: () => listDepartments({ business_unit_id: selectedPO?.business_unit_id, is_active: true }), enabled: open && Boolean(selectedPO?.department_id) && !selectedPO?.department_name });
  const locations = useQuery({ queryKey: ["locations", "receiving-dimensions", selectedPO?.business_unit_id], queryFn: () => listLocations({ business_unit_id: selectedPO?.business_unit_id, is_active: true }), enabled: open && Boolean(selectedPO?.location_id) && !selectedPO?.location_name });
  const businessUnitName = selectedPO?.business_unit_name ?? businessUnits.data?.find((item) => item.id === selectedPO?.business_unit_id)?.name ?? "—";
  const departmentName = selectedPO?.department_name ?? departments.data?.find((item) => item.id === selectedPO?.department_id)?.name ?? "—";
  const locationName = selectedPO?.location_name ?? locations.data?.find((item) => item.id === selectedPO?.location_id)?.name ?? "—";

  useEffect(() => {
    if (!open) return;
    setPurchaseOrderId(purchaseOrder?.id);
    setDestinationType("WAREHOUSE"); setWarehouseId(null); setReceivedAt(nowLocal()); setDeliveryNote(""); setNotes(""); setCostCorrectionReason(""); setLines([]);
  }, [open, purchaseOrder]);
  useEffect(() => {
    setLines((remaining.data ?? []).map((item: any) => ({ ...item, ordered_quantity: Number(item.ordered_quantity), received_quantity: Number(item.received_quantity), remaining_quantity: Number(item.remaining_quantity), quantity: 0, unit_cost: Number(item.unit_cost ?? 0), original_unit_cost: Number(item.unit_cost ?? 0), is_taxable: Boolean(item.is_taxable), tax_rate: Number(item.tax_rate ?? 0) })));
  }, [remaining.data]);
  const hasCostOverride = lines.some((line) => line.unit_cost !== line.original_unit_cost);
  const isPartial = lines.some((line) => line.quantity > 0 && line.quantity < line.remaining_quantity) || lines.some((line) => line.quantity === 0);
  const subtotal = useMemo(() => lines.reduce((sum, line) => sum + line.quantity * line.unit_cost, 0), [lines]);
  const taxAmount = useMemo(() => lines.reduce((sum, line) => sum + (line.is_taxable ? (line.quantity * line.unit_cost * Number(line.tax_rate || 0)) / 100 : 0), 0), [lines]);
  const updateQuantity = (id: number, value: number) => setLines((current) => current.map((line) => line.purchase_order_item_id === id ? { ...line, quantity: Math.min(Math.max(value, 0), line.remaining_quantity) } : line));
  const updateCost = (id: number, value: number) => setLines((current) => current.map((line) => line.purchase_order_item_id === id ? { ...line, unit_cost: value } : line));
  const submit = async () => {
    if (!purchaseOrderId) return alert("Select an approved purchase order.");
    if (destinationType === "WAREHOUSE" && !warehouseId) return alert("Warehouse is required.");
    if (!receivedAt || (isBeforeNow(receivedAt) && !canBackdate())) return alert("Receipt Date/Time cannot be before now.");
    const selected = lines.filter((line) => line.quantity > 0);
    if (!selected.length) return alert("Enter a received quantity greater than zero.");
    if (selected.some((line) => line.unit_cost <= 0)) return alert("Unit cost must be greater than zero.");
    if (hasCostOverride && !canCorrectCost) return alert("Only an authorized manager can override PO unit cost.");
    if (hasCostOverride && costCorrectionReason.trim().length < 3) return alert("Enter a correction reason.");
    try {
      await receive.mutateAsync({ purchaseOrderId, payload: { received_at: new Date(receivedAt).toISOString(), external_reference: deliveryNote || null, destination_type: destinationType, warehouse_id: destinationType === "WAREHOUSE" ? warehouseId : null, notes: notes || null, cost_correction_reason: hasCostOverride ? costCorrectionReason.trim() : null, items: selected.map((line) => ({ purchase_order_item_id: line.purchase_order_item_id, quantity: line.quantity, unit_cost: line.unit_cost })) } });
      onClose();
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      alert(typeof detail === "string" ? detail : "Goods receipt could not be saved");
    }
  };
  const poOptions=(receivable.data??[]).map((order:any)=>({id:order.id,label:`${order.po_number} — ${order.supplier_name ?? ""}`.trim(),keywords:[order.po_number??"",order.supplier_name??"",order.business_unit_name??"",order.department_name??"",order.location_name??""]}));
  const warehouseOptions=warehouses.filter((warehouse:any)=>warehouse.is_active).map((warehouse:any)=>({id:warehouse.id,label:`${warehouse.code} — ${warehouse.name}`,keywords:[warehouse.code??"",warehouse.name??""]}));

  return <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
    <DialogContent className="max-w-6xl">
      <DialogHeader><DialogTitle>Create Receiving Report</DialogTitle></DialogHeader>
      <DialogBody>
        <div className="space-y-4">
          {!purchaseOrder && <SearchableSelect label="Approved Purchase Order" required value={purchaseOrderId} disabled={receivable.isLoading} placeholder={receivable.isLoading ? "Loading approved POs..." : "Type PO number or supplier..."} options={poOptions} onChange={setPurchaseOrderId}/>} 
          {selectedPO && <div className="grid gap-3 rounded-lg border bg-slate-50 p-3 md:grid-cols-3"><div><span className="text-xs text-slate-500">Business Unit</span><div className="font-medium">{businessUnitName}</div></div><div><span className="text-xs text-slate-500">Department</span><div className="font-medium">{departmentName}</div></div><div><span className="text-xs text-slate-500">Location</span><div className="font-medium">{locationName}</div></div></div>}
          <div className="grid gap-3 md:grid-cols-2"><label>Receipt Date<input type="datetime-local" min={canBackdate()?undefined:nowLocal()} className="mt-1 h-9 w-full rounded-md border px-3 text-[13px]" value={receivedAt} onChange={(event) => setReceivedAt(event.target.value)}/></label><label>Delivery Note Number<input className="mt-1 h-9 w-full rounded-md border px-3 text-[13px]" value={deliveryNote} onChange={(event) => setDeliveryNote(event.target.value)}/></label></div>
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs leading-5 text-amber-900">Partial receiving is supported. Enter only the quantity physically received. Remaining quantities stay open for the next Receiving Report.{isPartial && <strong className="ml-1">This draft is a partial receipt.</strong>}</div>
          <label>Destination<select className="mt-1 h-9 w-full rounded-md border px-3 text-[13px]" value={destinationType} onChange={(event) => setDestinationType(event.target.value as "WAREHOUSE" | "DIRECT_USE")}><option value="WAREHOUSE">Warehouse</option><option value="DIRECT_USE">Direct Use</option></select></label>
          {destinationType === "WAREHOUSE" && <SearchableSelect label="Warehouse" required value={warehouseId ?? undefined} disabled={warehouses.length===0} placeholder="Type warehouse code or name..." options={warehouseOptions} onChange={(value)=>setWarehouseId(value ?? null)}/>} 
          {remaining.isLoading ? <p>Loading remaining PO items…</p> : !!lines.length && <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="w-full min-w-[900px] text-xs"><thead><tr><th className="w-[42%] p-2 text-left">Item</th><th className="w-24 p-2 text-right">Ordered</th><th className="w-28 p-2 text-right">Received</th><th className="w-24 p-2 text-right">Remaining</th><th className="w-28 p-2 text-right">Receive Now</th><th className="w-20 p-2 text-left">UOM</th><th className="w-40 p-2 text-left">Unit Cost</th></tr></thead><tbody>{lines.map((line) => <tr key={line.purchase_order_item_id} className="border-t"><td className="p-2"><div className="font-medium">{line.product_code} — {line.product_name}</div></td><td className="p-2 text-right">{line.ordered_quantity}</td><td className="p-2 text-right">{line.received_quantity}</td><td className="p-2 text-right font-semibold">{line.remaining_quantity}</td><td className="p-2"><input type="number" min="0" max={line.remaining_quantity} step="0.01" className="h-9 w-24 rounded-md border px-2 text-right text-[13px] tabular-nums" value={line.quantity} onChange={(event) => updateQuantity(line.purchase_order_item_id, Number(event.target.value))}/></td><td className="p-2">{line.uom ?? "—"}</td><td className="p-2">{canCorrectCost ? <div className="w-40"><CurrencyInput value={line.unit_cost} onValueChange={(value) => updateCost(line.purchase_order_item_id, value)}/></div> : money(line.unit_cost)}</td></tr>)}</tbody></table></div>}
          <div className="ml-auto w-full max-w-sm rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs tabular-nums">Subtotal <strong className="float-right">{money(subtotal)}</strong><br/>PPN (booked on invoice) <strong className="float-right">{money(taxAmount)}</strong><hr className="my-2"/>Grand Total <strong className="float-right">{money(subtotal + taxAmount)}</strong></div>
          {hasCostOverride && <textarea className="min-h-20 w-full rounded-md border p-2 text-[13px]" placeholder="Cost correction reason" value={costCorrectionReason} onChange={(event) => setCostCorrectionReason(event.target.value)}/>}<textarea className="min-h-20 w-full rounded-md border p-2 text-[13px]" placeholder="Notes" value={notes} onChange={(event) => setNotes(event.target.value)}/>
        </div>
      </DialogBody>
      <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={receive.isPending || !lines.length} onClick={submit}>Save Receiving Draft</Button></DialogFooter>
    </DialogContent>
  </Dialog>;
}
