import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import Dialog, { DialogBody, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import { userApi } from "@/modules/admin/users/userApi";
import { useProducts } from "@/modules/master/products/hooks/useProducts";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import { useApprovedPurchaseRequisitions } from "../hooks/usePurchaseOrders";
import PurchaseOrderHeader from "./PurchaseOrderHeader";
import PurchaseOrderItems, { PurchaseOrderItemRow } from "./PurchaseOrderItems";
import PurchaseOrderSummary from "./PurchaseOrderSummary";
import PurchaseOrderFooter from "./PurchaseOrderFooter";

interface Props { open:boolean; loading?:boolean; onClose:()=>void; onSubmit:(payload:any)=>Promise<void>|void }
type CreationType = "FROM_PR" | "DIRECT";
const today = () => new Date().toISOString().slice(0, 10);

export default function PurchaseOrderForm({open, loading, onClose, onSubmit}:Props) {
  const {data:suppliers=[]} = useSuppliers();
  const {data:approvedPRs=[]} = useApprovedPurchaseRequisitions();
  const {data:products=[]} = useProducts();
  const {data:departments=[]} = useQuery({queryKey:["user-departments"], queryFn:userApi.departments, enabled:open});
  const {data:locations=[]} = useQuery({queryKey:["user-locations"], queryFn:userApi.locations, enabled:open});
  const [creationType, setCreationType] = useState<CreationType>("FROM_PR");
  const [supplierId, setSupplierId] = useState<number>();
  const [selectedPR, setSelectedPR] = useState<any>();
  const [departmentId, setDepartmentId] = useState<number>();
  const [locationId, setLocationId] = useState<number>();
  const [orderDate, setOrderDate] = useState(today());
  const [expectedDate, setExpectedDate] = useState("");
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<PurchaseOrderItemRow[]>([]);

  useEffect(() => { if (open) { setCreationType("FROM_PR"); setSupplierId(undefined); setSelectedPR(undefined); setDepartmentId(undefined); setLocationId(undefined); setOrderDate(today()); setExpectedDate(""); setNotes(""); setItems([]); } }, [open]);
  const changeType = (type:CreationType) => { setCreationType(type); setSelectedPR(undefined); setItems([]); };
  const selectPR = (id:number) => {
    const requisition = approvedPRs.find((item:any) => item.id === id);
    setSelectedPR(requisition);
    setItems((requisition?.items ?? []).map((item:any) => ({
      product_code:item.product_code, product_name:item.product_name, description:item.description ?? "",
      uom:item.uom, requested_quantity:Number(item.quantity), remaining_quantity:Number(item.remaining_quantity),
      quantity:Number(item.remaining_quantity), unit_price:0, purchase_requisition_item_id:item.id,
    })));
  };
  const total = useMemo(() => items.reduce((sum, item) => sum + item.quantity * item.unit_price, 0), [items]);

  const save = async () => {
    if (!supplierId) return alert("Supplier is required.");
    if (creationType === "FROM_PR" && !selectedPR) return alert("Select one approved purchase requisition.");
    if (creationType === "DIRECT" && (!departmentId || !locationId)) return alert("Department and location are required for a direct purchase order.");
    if (creationType === "DIRECT" && (!orderDate || !expectedDate)) return alert("Order date and estimated delivery date are required.");
    if (!items.length) return alert(creationType === "FROM_PR" ? "The requisition has no eligible items." : "Add at least one item.");
    if (items.some((item) => !item.product_id && creationType === "DIRECT")) return alert("Select an item for every line.");
    if (items.some((item) => item.quantity <= 0 || item.unit_price < 0)) return alert("Quantities must be positive and unit costs cannot be negative.");
    if (creationType === "FROM_PR" && items.some((item) => item.quantity > Number(item.remaining_quantity))) return alert("Selected quantities cannot exceed the remaining PR quantities.");
    await onSubmit({
      supplier_id:supplierId,
      department_id:creationType === "DIRECT" ? departmentId : undefined,
      location_id:creationType === "DIRECT" ? locationId : undefined,
      order_date:creationType === "DIRECT" ? orderDate : today(),
      expected_date:creationType === "DIRECT" ? expectedDate : undefined,
      notes:creationType === "DIRECT" ? notes : undefined,
      purchase_requisition_ids:creationType === "FROM_PR" ? [selectedPR.id] : [],
      items:items.map(({product_code, product_name, requested_quantity, remaining_quantity, ...item}) => creationType === "FROM_PR" ? {...item, product_id:undefined, description:undefined, uom:undefined} : item),
    });
  };

  return <Dialog open={open} onOpenChange={(value) => !value && onClose()}><DialogContent className="flex max-h-[90vh] max-w-6xl flex-col overflow-hidden"><DialogHeader><DialogTitle>Create Purchase Order</DialogTitle></DialogHeader><DialogBody className="flex-1 overflow-y-auto">
    <fieldset className="mb-6 rounded-lg border border-slate-200 p-4"><legend className="px-2 font-semibold">Choose Creation Type</legend><div className="flex flex-wrap gap-6">
      <label className="flex items-center gap-2"><input type="radio" checked={creationType === "FROM_PR"} onChange={() => changeType("FROM_PR")}/> From Purchase Requisition</label>
      <label className="flex items-center gap-2"><input type="radio" checked={creationType === "DIRECT"} onChange={() => changeType("DIRECT")}/> Direct Purchase Order</label>
    </div></fieldset>
    <PurchaseOrderHeader fromRequisition={creationType === "FROM_PR"} suppliers={suppliers} approvedPRs={approvedPRs} departments={departments} locations={locations} supplierId={supplierId} selectedPR={selectedPR} departmentId={departmentId} locationId={locationId} orderDate={orderDate} expectedDate={expectedDate} notes={notes} onSupplierChange={setSupplierId} onSelectPR={selectPR} onDepartmentChange={setDepartmentId} onLocationChange={setLocationId} onOrderDateChange={setOrderDate} onExpectedDateChange={setExpectedDate} onNotesChange={setNotes}/>
    <div className="mt-8"><PurchaseOrderItems items={items} products={products} fromRequisition={creationType === "FROM_PR"} onChange={setItems}/></div>
    <div className="mt-8"><PurchaseOrderSummary total={total}/></div>
  </DialogBody><PurchaseOrderFooter loading={loading} onCancel={onClose} onSubmit={save}/></DialogContent></Dialog>;
}
