import InventoryPrintButton from "@/components/print/InventoryPrintButton";
import { inventoryDocumentReport } from "@/modules/warehouse/inventory/print/reports";
import InventoryReportHeading from "@/components/print/InventoryReportHeading";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import useAuthorization from "@/hooks/useAuthorization";
import ProductCombobox, { type ProductComboboxOption } from "@/components/form/ProductCombobox";
import SearchableSelect from "@/components/form/SearchableSelect";
import { listBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import { useWarehouses } from "@/modules/master/warehouses/hooks/useWarehouses";
import { storeRequestApi } from "./api";
import type { StoreRequest } from "./types";

const PAGE_SIZE = 25;
const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

export default function StoreRequestPage() {
  const { isSuperuser, hasPermission } = useAuthorization();
  const _canCreate = isSuperuser() || hasPermission("store_request.manage");
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("ALL");
  const [showCreate, setShowCreate] = useState(false);
  const [businessUnitId, setBusinessUnitId] = useState<number | undefined>();
  const [departmentId, setDepartmentId] = useState<number | undefined>();
  const [locationId, setLocationId] = useState<number | undefined>();
  const [warehouseId, setWarehouseId] = useState<number | undefined>();
  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<Array<{ product_id?: number; quantity: number; product?: ProductComboboxOption }>>([{ quantity: 0 }]);

  const listQuery = useQuery({ queryKey: ["store-requests", page, search, status], queryFn: async () => (await storeRequestApi.list({ page, page_size: PAGE_SIZE, search: search.trim() || undefined, status: status === "ALL" ? undefined : status })).data });
  const businessUnits = useQuery({ queryKey: ["business-units"], queryFn: listBusinessUnits });
  const departments = useQuery({ queryKey: ["departments", businessUnitId, locationId], queryFn: () => listDepartments({ business_unit_id: businessUnitId, location_id: locationId, is_active: true }), enabled: !!businessUnitId && !!locationId });
  const locations = useQuery({ queryKey: ["locations", businessUnitId], queryFn: () => listLocations(businessUnitId ?? {}), enabled: !!businessUnitId });
  const warehouses = useWarehouses();
  const locationWarehouses = useMemo(() => (warehouses.data ?? []).filter((row) => row.is_active && row.location_id === locationId), [warehouses.data, locationId]);
  const productIds = useMemo(() => items.flatMap((row) => row.product_id ? [row.product_id] : []), [items]);
  const availability = useQuery({ queryKey: ["store-request-availability", warehouseId, productIds], queryFn: async () => (await storeRequestApi.availability(warehouseId!, productIds)).data, enabled: !!warehouseId && productIds.length > 0 });
  const stockByProduct = useMemo(() => new Map((availability.data ?? []).map((row) => [row.product_id, Number(row.available_stock || 0)])), [availability.data]);
  const hasShortage = items.some((row) => row.product_id && row.quantity > (stockByProduct.get(row.product_id) ?? 0));

  const createMutation = useMutation({
    mutationFn: () => {
      if (!businessUnitId || !departmentId || !locationId || !warehouseId) throw new Error("Complete Business Unit, Department, Location, and Warehouse");
      const validItems = items.filter((row) => row.product_id && row.quantity > 0).map((row) => ({ product_id: row.product_id!, quantity: row.quantity }));
      if (!validItems.length) throw new Error("Add at least one item with quantity greater than zero");
      if (availability.isLoading) throw new Error("Wait for warehouse stock to finish loading");
      if (hasShortage) throw new Error("Requested quantity exceeds available warehouse stock");
      return storeRequestApi.create({ business_unit_id: businessUnitId, department_id: departmentId, location_id: locationId, warehouse_id: warehouseId, notes: notes || null, items: validItems });
    },
    onSuccess: async (response) => { await qc.invalidateQueries({ queryKey: ["store-requests"] }); setShowCreate(false); navigate(`/store-requests/${response.data.id}`); },
  });

  const payload: any = listQuery.data ?? {};
  const rows: StoreRequest[] = payload.items ?? [];
  const pages = Math.max(payload.total_pages ?? 0, 1);
  const total = payload.total_items ?? 0;
  const statusOptions = useMemo(() => ["ALL", "DRAFT", "PENDING_APPROVAL", "APPROVED", "PARTIALLY_ISSUED", "ISSUED", "REJECTED"], []);
  const businessUnitOptions=(businessUnits.data??[]).filter((row:any)=>row.is_active).map((row:any)=>({id:row.id,label:`${row.code ?? ""}${row.code ? " — " : ""}${row.name}`,keywords:[row.code??"",row.name??""]}));
  const locationOptions=(locations.data??[]).filter((row:any)=>row.is_active).map((row:any)=>({id:row.id,label:`${row.code ?? ""}${row.code ? " — " : ""}${row.name}`,keywords:[row.code??"",row.name??""]}));
  const departmentOptions=(departments.data??[]).filter((row:any)=>row.is_active).map((row:any)=>({id:row.id,label:`${row.code ?? ""}${row.code ? " — " : ""}${row.name}`,keywords:[row.code??"",row.name??""]}));
  const warehouseOptions=locationWarehouses.map((row:any)=>({id:row.id,label:`${row.code} — ${row.name}`,keywords:[row.code??"",row.name??""]}));

  return <div className="inventory-print-report space-y-6">
<InventoryReportHeading title="Store Request" context={`Search: ${search || "All"} · Status: ${status}`} rows={rows.length} total={total}/>
    <PageHeader title="Store Request" description="Internal warehouse stock requests and goods issue tracking." actions={<>
_canCreate ? <Button onClick={() => {setShowCreate(true);setBusinessUnitId(undefined);setLocationId(undefined);setDepartmentId(undefined);setWarehouseId(undefined);setItems([{quantity:0}]);setNotes("")}}>Create Store Request</Button> : undefined
<InventoryPrintButton loadReport={() => inventoryDocumentReport("requests",{status:status === "ALL" ? undefined : status,search:search.trim() || undefined}, `Search: ${search || "All"} · Status: ${status}`)}/>
</>} />
    <Card className="p-4 print:hidden"><div className="grid gap-3 md:grid-cols-[1fr_220px]"><input className={input} placeholder="Search SR number or requester" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} /><select className={input} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>{statusOptions.map((value) => <option key={value} value={value}>{value.replaceAll("_", " ")}</option>)}</select></div></Card>
    <Card className="p-0"><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-xs"><thead><tr><th className="px-4 py-3 text-left">SR Number</th><th className="px-4 py-3 text-left">Date</th><th className="px-4 py-3 text-left">Requester</th><th className="px-4 py-3 text-left">Warehouse</th><th className="px-4 py-3 text-left">Department</th><th className="px-4 py-3 text-right">Remaining</th><th className="px-4 py-3 text-left">Status</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-t whitespace-nowrap"><td className="px-4 py-3 font-medium"><Link className="text-emerald-700 hover:underline" to={`/store-requests/${row.id}`}>{row.sr_number}</Link></td><td className="px-4 py-3">{row.request_date}</td><td className="px-4 py-3">{row.requester_name ?? "—"}</td><td className="px-4 py-3">{row.warehouse_name ?? "—"}</td><td className="px-4 py-3">{row.department_name ?? "—"}</td><td className="px-4 py-3 text-right tabular-nums">{Number(row.total_remaining_quantity ?? 0).toLocaleString("id-ID")}</td><td className="px-4 py-3">{row.status.replaceAll("_", " ")}</td></tr>)}</tbody></table></div><div className="p-4 print:hidden"><Pagination page={page} pages={pages} total={total} pageSize={PAGE_SIZE} noun="store requests" onChange={setPage} /></div></Card>

    {showCreate && <div className="fixed inset-0 z-[80] grid place-items-center bg-black/40 p-4"><div className="max-h-[90vh] w-full max-w-5xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl"><div className="mb-5 flex items-center justify-between"><div><h2 className="text-lg font-semibold">Create Store Request</h2><p className="text-xs text-slate-500">Request stock from a warehouse for internal use.</p></div><Button variant="secondary" onClick={() => setShowCreate(false)}>Close</Button></div>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4"><SearchableSelect label="Business Unit" required value={businessUnitId} placeholder="Type business unit..." options={businessUnitOptions} onChange={(id)=>{setBusinessUnitId(id);setLocationId(undefined);setDepartmentId(undefined);setWarehouseId(undefined)}}/><SearchableSelect label="Location" required value={locationId} disabled={!businessUnitId} placeholder="Type location..." options={locationOptions} onChange={(id)=>{setLocationId(id);setDepartmentId(undefined);setWarehouseId(undefined)}}/><SearchableSelect label="Department" required value={departmentId} disabled={!locationId} placeholder="Type department..." options={departmentOptions} onChange={setDepartmentId}/><SearchableSelect label="Warehouse" required value={warehouseId} disabled={!locationId} placeholder="Type warehouse code or name..." options={warehouseOptions} onChange={setWarehouseId}/></div>
      <div className="mt-5 space-y-3">{items.map((row, index) => { const available=row.product_id?(stockByProduct.get(row.product_id)??0):0; const shortage=Boolean(row.product_id&&row.quantity>available); return <div key={index} className="grid gap-3 md:grid-cols-[minmax(0,1fr)_150px_180px_80px]"><ProductCombobox remote value={row.product_id} onChange={(productId) => setItems((old) => old.map((item, i) => i === index ? { ...item, product_id: productId } : item))} onSelect={(product) => setItems((old) => old.map((item, i) => i === index ? { ...item, product } : item))} /><div className={`flex h-10 items-center rounded-md border px-3 text-sm ${shortage?"border-red-300 bg-red-50 text-red-700":"border-slate-200 bg-slate-50 text-slate-600"}`}>Available: {availability.isLoading?"…":available.toLocaleString("id-ID")}</div><input className={`${input} ${shortage?"border-red-400":""}`} type="number" min="0" max={available} step="0.01" placeholder="Quantity" value={row.quantity || ""} onChange={(e) => setItems((old) => old.map((item, i) => i === index ? { ...item, quantity: Number(e.target.value) } : item))} /><Button variant="secondary" onClick={() => setItems((old) => old.length === 1 ? old : old.filter((_, i) => i !== index))}>Remove</Button></div>})}</div>
      <button className="mt-3 text-sm font-medium text-emerald-700" onClick={() => setItems((old) => [...old, { quantity: 0 }])}>+ Add Item</button>
      <textarea className="mt-5 min-h-20 w-full rounded-md border border-slate-300 p-3 text-sm" placeholder="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />
      {createMutation.error && <div className="mt-3 text-sm text-red-600">{createMutation.error instanceof Error ? createMutation.error.message : "Unable to create Store Request"}</div>}
      <div className="mt-5 flex justify-end gap-2"><Button variant="secondary" onClick={() => setShowCreate(false)}>Cancel</Button><Button disabled={createMutation.isPending || availability.isLoading || hasShortage} onClick={() => createMutation.mutate()}>{createMutation.isPending ? "Saving..." : "Create"}</Button></div>
    </div></div>}
  </div>;
}
