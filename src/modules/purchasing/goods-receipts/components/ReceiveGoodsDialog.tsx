import "../receiving-lines.css";
import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
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
import { isBeforeToday, nowLocal } from "@/utils/dateConstraints";
import {
  useReceivablePurchaseOrders,
  useReceiveGoods,
  useRemainingPurchaseOrderItems,
} from "../hooks/useGoodsReceipts";

import ReceivingDestinationField from "./ReceivingDestinationField";
import ReceivingBillingFields from "./ReceivingBillingFields";
import { emptyReceivingBilling, receivingBillingPayload, validateReceivingBilling } from "../billing";
import { destinationFor, destinationError, type LineRouting } from "../destination";
import { mapPurchasingFieldPaths, readPurchasingError, usePurchasingFieldErrors } from "../../fieldErrors";
import { PURCHASING_FIELD, PURCHASING_LINE_INPUT, PURCHASING_SMALL_INPUT, PURCHASING_TEXTAREA } from "../../components/purchasingFields";

interface Props {
  open: boolean;
  purchaseOrder?: PurchaseOrder | null;
  onClose: () => void;
}
interface ReceiveLine extends LineRouting {
  purchase_order_item_id: number;
  expense_account_id?: number | null;
  catalog_type?: "CATERING" | "HOTEL";
  inventory_treatment?: string;
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
  const { isSuperuser, canAccess, hasPermission } = useAuthorization();
  const canCorrectCost = isSuperuser() || canAccess(["GENERAL MANAGER", "FINANCE MANAGER", "PURCHASING MANAGER", "PROCUREMENT MANAGER"]);
  const receivable = useReceivablePurchaseOrders(open && !purchaseOrder);
  const [purchaseOrderId, setPurchaseOrderId] = useState<number>();
  const remaining = useRemainingPurchaseOrderItems(purchaseOrderId);
  const receive = useReceiveGoods();
  const [warehouseId, setWarehouseId] = useState<number | null>(null);
  const [receivedAt, setReceivedAt] = useState(nowLocal());
  const [historical, setHistorical] = useState(false);
  const [deliveryNote, setDeliveryNote] = useState("");
  const [notes, setNotes] = useState("");
  const [billing, setBilling] = useState(emptyReceivingBilling);
  const [costCorrectionReason, setCostCorrectionReason] = useState("");
  const fieldErrors = usePurchasingFieldErrors(open);
  const [lines, setLines] = useState<ReceiveLine[]>([]);
  const hasWarehouse = lines.some(line => line.quantity > 0 && destinationFor(line) === "WAREHOUSE");
  const hasDirectUse = lines.some(line => destinationFor(line) === "DIRECT_USE" && line.inventory_treatment !== "FIXED_ASSET");
  const expenses=useQuery({queryKey:["receiving-expense-accounts"],queryFn:()=>getAllAccountLookup({account_type:"EXPENSE",is_active:true,is_posting:true}),enabled:open && hasDirectUse});
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
    setHistorical(false); setWarehouseId(null); setReceivedAt(nowLocal()); setDeliveryNote(""); setNotes(""); setCostCorrectionReason(""); setLines([]); setBilling(emptyReceivingBilling());
  }, [open, purchaseOrder]);
  useEffect(() => {
    setLines((remaining.data ?? []).map((item: any) => ({ ...item, ordered_quantity: Number(item.ordered_quantity), received_quantity: Number(item.received_quantity), remaining_quantity: Number(item.remaining_quantity), quantity: 0, unit_cost: Number(item.unit_cost ?? 0), original_unit_cost: Number(item.unit_cost ?? 0), expense_account_id: item.purchase_account_id ?? null, destination_type: null, is_taxable: !!item.is_taxable, tax_rate: item.is_taxable ? Number(item.tax_rate??0) : 0 })));
  }, [remaining.data]);
  const hasCostOverride = lines.some((line) => line.unit_cost !== line.original_unit_cost);
  const isPartial = lines.some((line) => line.quantity > 0 && line.quantity < line.remaining_quantity) || lines.some((line) => line.quantity === 0);
  const subtotal = useMemo(() => lines.reduce((sum, line) => sum + line.quantity * line.unit_cost, 0), [lines]);
  const taxAmount = useMemo(() => lines.reduce((sum, line) => sum + (line.is_taxable ? (line.quantity * line.unit_cost * Number(line.tax_rate || 0)) / 100 : 0), 0), [lines]);
  const updateQuantity = (id: number, value: number) => setLines((current) => current.map((line) => line.purchase_order_item_id === id ? { ...line, quantity: Math.min(Math.max(value, 0), line.remaining_quantity) } : line));
  const updateCost = (id: number, value: number) => setLines((current) => current.map((line) => line.purchase_order_item_id === id ? { ...line, unit_cost: value } : line));
  const submit = async () => {
    const fail = (field: string, message: string) => { fieldErrors.setLocal(field, message); return undefined; };
    if (!purchaseOrderId) return fail("purchase_order_id", "Select an approved purchase order.");
    if (hasWarehouse && !warehouseId) return fail("warehouse_id", "Warehouse is required.");
    if (!receivedAt || receivedAt < "2026-01-01T00:00") return fail("received_at", "Receiving dated before 2026 is excluded from stock.");
    if (historical && !isBeforeToday(receivedAt)) return fail("received_at", "Historical entry requires a past business date.");

    const selected = lines.filter((line) => line.quantity > 0);
    const selectedIndexes = lines.map((line, index) => line.quantity > 0 ? index : -1).filter((index) => index >= 0);
    if (!selected.length) return fail("items[0].quantity", "Enter a received quantity greater than zero.");
    const routingIndex = selectedIndexes.find((index) => Boolean(destinationError(selected[selectedIndexes.indexOf(index)])));
    if (routingIndex !== undefined) return fail(`items[${routingIndex}].destination_type`, destinationError(lines[routingIndex]) || "Choose a destination for every received item.");
    const expenseIndex = selectedIndexes.find((index) => {
      const line = lines[index];
      return destinationFor(line) === "DIRECT_USE" && line.catalog_type === "HOTEL" && line.inventory_treatment !== "FIXED_ASSET" && !line.expense_account_id;
    });
    if (expenseIndex !== undefined) return fail(`items[${expenseIndex}].expense_account_id`, "Choose an expense destination for each Hotel item in the PO department.");
    const costIndex = selectedIndexes.find((index) => lines[index].unit_cost <= 0);
    if (costIndex !== undefined) return fail(`items[${costIndex}].unit_cost`, "Unit cost must be greater than zero.");
    if (hasCostOverride && !canCorrectCost) return fail("cost_correction_reason", "Only an authorized manager can override PO unit cost.");
    if (hasCostOverride && costCorrectionReason.trim().length < 3) return fail("cost_correction_reason", "Enter a correction reason.");
    const billingIssue = validateReceivingBilling(billing, subtotal);
    if (billingIssue) return fail("billing", billingIssue);
    fieldErrors.clear();
    try {
      await receive.mutateAsync({ purchaseOrderId, payload: { source_type: historical ? "HISTORICAL_ENTRY" : "LIVE", received_at: new Date(receivedAt).toISOString(), external_reference: deliveryNote || null, warehouse_id: hasWarehouse ? warehouseId : null, notes: notes || null, cost_correction_reason: hasCostOverride ? costCorrectionReason.trim() : null, ...receivingBillingPayload(billing), items: selected.map((line) => ({ purchase_order_item_id: line.purchase_order_item_id, quantity: line.quantity, unit_cost: line.unit_cost, is_taxable:Number(line.tax_rate||0)>0, tax_rate:Number(line.tax_rate||0), destination_type:line.destination_type ?? null, destination_override_reason:line.destination_override_reason || null, expense_account_id:destinationFor(line) === "DIRECT_USE" ? line.expense_account_id ?? null : null })) } });
      onClose();
    } catch (error) {
      const info = readPurchasingError(error);
      fieldErrors.show(mapPurchasingFieldPaths(info, (path) => path.replace(/^items\[(\d+)\]/, (_, index: string) => `items[${selectedIndexes[Number(index)] ?? Number(index)}]`)));
    }
  };
  const poOptions=(receivable.data??[]).map((order:any)=>({id:order.id,label:`${order.po_number} · ${order.expected_date ?? "Unscheduled"} — ${order.supplier_name ?? ""}`.trim(),keywords:[order.po_number??"",order.supplier_name??"",order.business_unit_name??"",order.department_name??"",order.location_name??""]}));
  const warehouseOptions=warehouses.filter((warehouse:any)=>warehouse.is_active && Number(warehouse.location_id) === Number(selectedPO?.location_id)).map((warehouse:any)=>({id:warehouse.id,label:`${warehouse.code} — ${warehouse.name}`,keywords:[warehouse.code??"",warehouse.name??""]}));

  return <Dialog open={open} onOpenChange={(value) => !value && onClose()}>
    <DialogContent className="max-w-[1440px]">
      <DialogHeader><DialogTitle>Create Receiving Report</DialogTitle></DialogHeader>
      <DialogBody>
        <div className="space-y-4">
          {fieldErrors.message && <div role="alert" className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm font-medium text-red-700">{fieldErrors.message}</div>}
          {hasPermission("receiving.post") && <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={historical} onChange={event => setHistorical(event.target.checked)}/> Historical entry (Draft → Post)</label>}
          {historical && <div className="rounded-md border border-blue-200 bg-blue-50 px-3 py-2 text-xs leading-5 text-blue-900">Choose the exact past business date. The period must be open and allow backdated entries; normal receiving approval is skipped.</div>}
          {!purchaseOrder && <div><SearchableSelect label="Approved Purchase Order" required dataField="purchase_order_id" invalid={Boolean(fieldErrors.errors.purchase_order_id)} value={purchaseOrderId} disabled={receivable.isLoading} placeholder={receivable.isLoading ? "Loading approved POs..." : "Type PO number or supplier..."} options={poOptions} onChange={setPurchaseOrderId}/>{fieldErrors.fieldError("purchase_order_id")}</div>}
          {selectedPO && <div className="grid gap-3 rounded-lg border bg-slate-50 p-3 md:grid-cols-3"><div><span className="text-xs text-slate-500">Business Unit</span><div className="font-medium">{businessUnitName}</div></div><div><span className="text-xs text-slate-500">Department</span><div className="font-medium">{departmentName}</div></div><div><span className="text-xs text-slate-500">Location</span><div className="font-medium">{locationName}</div></div></div>}
          <div className="grid gap-3 md:grid-cols-2"><label>Receipt Date<input type="datetime-local" disabled={!historical} data-accounting-date="true" data-min-date="2026-01-01" data-field="received_at" min="2026-01-01T00:00" className={`mt-1 ${PURCHASING_FIELD}`} value={receivedAt} onChange={(event) => setReceivedAt(event.target.value)}/>{fieldErrors.fieldError("received_at")}{!historical && <div className="mt-1 text-[11px] text-slate-500">Current receipts use today’s business date.</div>}</label><label>Delivery Note Number<input className={`mt-1 ${PURCHASING_FIELD}`} value={deliveryNote} onChange={(event) => setDeliveryNote(event.target.value)}/></label></div>
          <div className="rounded-md border border-amber-200 bg-amber-50 px-3 py-2.5 text-xs leading-5 text-amber-900">Partial receiving is supported. Enter only the quantity physically received. Remaining quantities stay open for the next Receiving Report.{isPartial && <strong className="ml-1">This draft is a partial receipt.</strong>}</div>

          {hasWarehouse && <div><SearchableSelect label="Warehouse" required dataField="warehouse_id" invalid={Boolean(fieldErrors.errors.warehouse_id)} value={warehouseId ?? undefined} disabled={warehouses.length===0} placeholder="Type warehouse code or name..." options={warehouseOptions} onChange={(value)=>setWarehouseId(value ?? null)}/>{fieldErrors.fieldError("warehouse_id")}</div>}
          {remaining.isLoading ? <p>Loading remaining PO items…</p> : !!lines.length && <div className="overflow-x-auto rounded-lg border border-slate-200"><table className="receiving-lines receiving-lines-po"><colgroup><col/><col className="rl-po-quantity"/><col className="rl-po-quantity"/><col className="rl-po-quantity"/><col className="rl-quantity"/><col className="rl-destination"/><col className="rl-unit"/><col className="rl-cost"/><col className="rl-tax-rate"/>{hasDirectUse && <col className="rl-expense"/>}</colgroup><thead><tr><th className="p-2 text-left">Item</th><th className="p-2 text-right">Ordered</th><th className="p-2 text-right">Received</th><th className="p-2 text-right">Remaining</th><th className="p-2 text-right">Qty</th><th className="p-2 text-left">Destination</th><th className="p-2 text-left">UOM</th><th className="whitespace-nowrap p-2 text-left">Unit Cost</th><th className="p-2">PPN %</th>{hasDirectUse && <th className="p-2 text-left">Expense destination</th>}</tr></thead><tbody>{lines.map((line) => <tr key={line.purchase_order_item_id} className="border-t"><td className="p-2"><div className="font-medium">{line.product_code} — {line.product_name}</div></td><td className="p-2 text-right">{line.ordered_quantity}</td><td className="p-2 text-right">{line.received_quantity}</td><td className="p-2 text-right font-semibold">{line.remaining_quantity}</td><td className="p-2"><div><input type="number" min="0" max={line.remaining_quantity} step="0.01" data-field={`items[${lines.indexOf(line)}].quantity`} className={`${PURCHASING_LINE_INPUT} w-24 !text-right ${fieldErrors.errors[`items[${lines.indexOf(line)}].quantity`] ? "border-red-500 ring-2 ring-red-200" : ""}`} value={line.quantity} onChange={(event) => updateQuantity(line.purchase_order_item_id, Number(event.target.value))}/>{fieldErrors.fieldError(`items[${lines.indexOf(line)}].quantity`)}</div></td><td className="p-2"><div data-field={`items[${lines.indexOf(line)}].destination_type`}><ReceivingDestinationField name={line.product_name} line={line} onChange={value => setLines(current => current.map(item => item.purchase_order_item_id === line.purchase_order_item_id ? {...item,...value} : item))}/>{fieldErrors.fieldError(`items[${lines.indexOf(line)}].destination_type`)}</div></td><td className="p-2">{line.uom ?? "—"}</td><td className="p-2">{canCorrectCost ? <div className="min-w-0"><CurrencyInput value={line.unit_cost} dataField={`items[${lines.indexOf(line)}].unit_cost`} invalid={Boolean(fieldErrors.errors[`items[${lines.indexOf(line)}].unit_cost`])} onValueChange={(value) => updateCost(line.purchase_order_item_id, value)}/>{fieldErrors.fieldError(`items[${lines.indexOf(line)}].unit_cost`)}</div> : money(line.unit_cost)}</td><td className="p-2"><input aria-label={`PPN rate for ${line.product_name}`} type="number" min="0" max="100" step="0.01" className={PURCHASING_SMALL_INPUT} value={line.tax_rate??0} onChange={e=>setLines(current=>current.map(item=>item.purchase_order_item_id===line.purchase_order_item_id?{...item,tax_rate:Number(e.target.value),is_taxable:Number(e.target.value)>0}:item))}/></td>{hasDirectUse && <td className="p-2">{destinationFor(line) === "DIRECT_USE" && line.inventory_treatment !== "FIXED_ASSET" ? <div><select aria-label={`Expense destination for ${line.product_name}`} data-field={`items[${lines.indexOf(line)}].expense_account_id`} className={`w-full rounded border p-2 ${fieldErrors.errors[`items[${lines.indexOf(line)}].expense_account_id`] ? "border-red-500 ring-2 ring-red-200" : ""}`} value={line.expense_account_id ?? ""} onChange={e=>setLines(current=>current.map(item=>item.purchase_order_item_id === line.purchase_order_item_id ? {...item,expense_account_id:Number(e.target.value)||null}:item))}><option value="">Item expense mapping</option>{expenses.data?.map(account=><option key={account.id} value={account.id}>{account.account_code} — {account.account_name}</option>)}</select>{fieldErrors.fieldError(`items[${lines.indexOf(line)}].expense_account_id`)}</div> : "—"}</td>}</tr>)}</tbody></table></div>}
          <div className="ml-auto w-full max-w-sm rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs tabular-nums">Subtotal <strong className="float-right">{money(subtotal)}</strong><br/>PPN estimate · verified on supplier invoice <strong className="float-right">{money(taxAmount)}</strong><hr className="my-2"/>Grand Total <strong className="float-right">{money(subtotal + taxAmount)}</strong></div>
          <div data-field="billing"><ReceivingBillingFields value={billing} onChange={setBilling} subtotal={subtotal} tax={taxAmount} open={open}/>{fieldErrors.fieldError("billing")}</div>
          {hasCostOverride && <div><textarea data-field="cost_correction_reason" className={`${PURCHASING_TEXTAREA} ${fieldErrors.errors.cost_correction_reason ? "border-red-500 ring-2 ring-red-200" : ""}`} placeholder="Cost correction reason" value={costCorrectionReason} onChange={(event) => setCostCorrectionReason(event.target.value)}/>{fieldErrors.fieldError("cost_correction_reason")}</div>}<textarea className={PURCHASING_TEXTAREA} placeholder="Notes" value={notes} onChange={(event) => setNotes(event.target.value)}/>
        </div>
      </DialogBody>
      <DialogFooter><Button variant="outline" onClick={onClose}>Cancel</Button><Button disabled={receive.isPending || !lines.length} onClick={submit}>{historical ? "Save Historical Entry" : "Save Receiving Draft"}</Button></DialogFooter>
    </DialogContent>
  </Dialog>;
}

