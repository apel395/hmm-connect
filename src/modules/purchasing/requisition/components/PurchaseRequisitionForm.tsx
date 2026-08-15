import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import Dialog, { DialogContent } from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";
import Textarea from "@/components/ui/Textarea";
import SearchableSelect from "@/components/form/SearchableSelect";
import { filterBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import { isBeforeDate, isBeforeToday, todayLocal } from "@/utils/dateConstraints";

import PurchaseRequisitionItems, { PurchaseRequisitionItemRow, Product } from "./PurchaseRequisitionItems";

interface Props {
  onClose: () => void;
  onSubmit: (payload: any) => Promise<void>;
  initialData?: any;
}

export default function PurchaseRequisitionForm({ onClose, onSubmit, initialData }: Props) {
  const editing = Boolean(initialData);
  const [businessUnitId, setBusinessUnitId] = useState<number>();
  const [departmentId, setDepartmentId] = useState<number>();
  const [locationId, setLocationId] = useState<number>();
  const [notes, setNotes] = useState("");
  const [expiryDate, setExpiryDate] = useState("");
  const [requestDate, setRequestDate] = useState("");
  const [saving, setSaving] = useState(false);
  const [products, setProducts] = useState<Product[]>([]);
  const [items, setItems] = useState<PurchaseRequisitionItemRow[]>([{ product_id: 0, quantity: 1, estimated_price: 0 }]);

  const businessUnits = useQuery({ queryKey: ["business-units", "pr-form"], queryFn: () => filterBusinessUnits({ is_active: true }) });
  const departments = useQuery({ queryKey: ["departments", "pr-form", businessUnitId], queryFn: () => listDepartments({ business_unit_id: businessUnitId, is_active: true }), enabled: Boolean(businessUnitId) });
  const locations = useQuery({ queryKey: ["locations", "pr-form", businessUnitId], queryFn: () => listLocations({ business_unit_id: businessUnitId, is_active: true }), enabled: Boolean(businessUnitId) });
  const activeDepartments = useMemo(() => departments.data ?? [], [departments.data]);
  const activeLocations = useMemo(() => locations.data ?? [], [locations.data]);

  useEffect(() => {
    if (initialData) {
      setBusinessUnitId(initialData.business_unit_id ?? undefined);
      setDepartmentId(initialData.department_id ?? undefined);
      setLocationId(initialData.location_id ?? undefined);
      setNotes(initialData.notes ?? "");
      setExpiryDate(initialData.expiry_date ?? "");
      setRequestDate(initialData.request_date ?? "");
      setProducts((initialData.items ?? []).map((item: any) => ({
        id: Number(item.product_id),
        code: item.product_code,
        name: item.product_name,
        uom: item.uom,
        tax_category: item.tax_category,
        is_taxable: item.is_taxable,
        tax_rate: item.tax_rate,
      })));
      setItems((initialData.items ?? []).map((item: any) => ({
        product_id: Number(item.product_id),
        quantity: Number(item.quantity),
        estimated_price: Number(item.estimated_price),
      })));
    } else {
      setProducts([]);
      setRequestDate(todayLocal());
      setExpiryDate("");
    }
  }, [initialData]);

  function rememberProduct(product: Product) {
    setProducts((current) => current.some((item) => item.id === product.id)
      ? current.map((item) => item.id === product.id ? { ...item, ...product } : item)
      : [...current, product]);
  }

  function changeBusinessUnit(id?: number) {
    setBusinessUnitId(id);
    setDepartmentId(undefined);
    setLocationId(undefined);
  }

  async function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    const validItems = items.filter((item) => item.product_id > 0 && item.quantity > 0 && item.estimated_price >= 0);
    if (!businessUnitId) return alert("Business Unit is required.");
    if (!departmentId) return alert("Department is required.");
    if (!locationId) return alert("Location is required.");
    if (!editing && (!requestDate || isBeforeToday(requestDate))) return alert("Request Date cannot be before today.");
    if (!editing && expiryDate && isBeforeDate(expiryDate, requestDate || todayLocal())) return alert("Valid Until cannot be before Request Date.");
    if (!validItems.length) return alert("Please add valid products.");
    try {
      setSaving(true);
      await onSubmit({
        business_unit_id: businessUnitId,
        department_id: departmentId,
        location_id: locationId,
        request_date: requestDate || undefined,
        notes,
        expiry_date: expiryDate || null,
        items: validItems,
      });
      onClose();
    } finally { setSaving(false); }
  }

  const fieldClass = "mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
  const createMinimum = editing ? undefined : todayLocal();
  return <Dialog open onOpenChange={(open) => !open && onClose()}><DialogContent className="max-h-[90vh] max-w-6xl overflow-hidden p-0">
    <form onSubmit={handleSubmit} className="flex h-full flex-col">
      <div className="shrink-0 border-b border-slate-200 px-6 py-5"><h2 className="text-xl font-semibold">{editing ? "Edit Purchase Requisition" : "Create Purchase Requisition"}</h2><p className="mt-1 text-sm text-slate-500">{editing ? "Update all requisition details except the PR number." : "Create a purchasing request before approval and purchase order creation."}</p></div>
      <div className="max-h-[70vh] space-y-6 overflow-y-auto p-6">
        <div className="grid gap-5 md:grid-cols-2 lg:grid-cols-4">
          <label className="text-sm font-medium">Business Unit<SearchableSelect className="mt-1" value={businessUnitId} options={businessUnits.data ?? []} placeholder="Type business unit..." onChange={(id) => changeBusinessUnit(id || undefined)} /></label>
          <label className="text-sm font-medium">Department<SearchableSelect className="mt-1" value={departmentId} options={activeDepartments} disabled={!businessUnitId || departments.isLoading} placeholder="Type department..." onChange={(id) => setDepartmentId(id || undefined)} /></label>
          <label className="text-sm font-medium">Location<SearchableSelect className="mt-1" value={locationId} options={activeLocations} disabled={!businessUnitId || locations.isLoading} placeholder="Type location..." onChange={(id) => setLocationId(id || undefined)} /></label>
          <label className="text-sm font-medium">Request Date<input type="date" min={createMinimum} value={requestDate} onChange={(e) => setRequestDate(e.target.value)} className={fieldClass}/></label>
          <label className="text-sm font-medium">Valid Until<input type="date" min={editing ? undefined : (requestDate || todayLocal())} value={expiryDate} onChange={(e) => setExpiryDate(e.target.value)} className={fieldClass}/></label>
        </div>
        <div><label className="mb-2 block text-sm font-medium">Purpose / Notes</label><Textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)}/></div>
        <PurchaseRequisitionItems items={items} products={products} onChange={setItems} onProductLoaded={rememberProduct}/>
      </div>
      <div className="flex shrink-0 justify-end gap-3 border-t border-slate-200 px-6 py-4"><Button type="button" variant="outline" onClick={onClose}>Cancel</Button><Button type="submit" loading={saving}>{editing ? "Save Changes" : "Create Purchase Requisition"}</Button></div>
    </form>
  </DialogContent></Dialog>;
}
