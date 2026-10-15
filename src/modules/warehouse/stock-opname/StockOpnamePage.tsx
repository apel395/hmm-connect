import DataWorkspace from "@/components/workspace/DataWorkspace";
import InventoryPrintButton from "@/components/print/InventoryPrintButton";
import { inventoryDocumentReport } from "@/modules/warehouse/inventory/print/reports";
import InventoryReportHeading from "@/components/print/InventoryReportHeading";
import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import { SlidersHorizontal } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import SearchableSelect from "@/components/form/SearchableSelect";
import { listDepartments, listLocations } from "@/modules/admin/organization/api";
import { useWarehouses } from "@/modules/master/warehouses/hooks/useWarehouses";
import { stockOpnameApi } from "./api";

const PAGE_SIZE = 50;
const input = "h-8 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

export default function StockOpnamePage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [showFilters, setShowFilters] = useState(false);
  const [status, setStatus] = useState("ALL");
  const [show, setShow] = useState(false);
  const [warehouseId, setWarehouseId] = useState<number>();
  const [locationId, setLocationId] = useState<number>();
  const [departmentId, setDepartmentId] = useState<number>();
  const departments=useQuery({queryKey:["opname-departments",locationId],queryFn:()=>listDepartments({location_id:locationId,is_active:true}),enabled:show && Boolean(locationId)});
  const [notes, setNotes] = useState("");
  const warehouses = useWarehouses();
  const locationWarehouses = useMemo(
    () => (warehouses.data ?? []).filter((warehouse) => warehouse.is_active && (!locationId || warehouse.location_id === locationId)),
    [warehouses.data, locationId],
  );
  const locations = useQuery({ queryKey: ["organization-locations", "active"], queryFn: () => listLocations({ is_active: true }) });
  useEffect(() => {
    if (show && locations.data?.length === 1 && !locationId) setLocationId(locations.data[0].id);
  }, [show, locations.data, locationId]);
  useEffect(() => {
    if (warehouseId && !locationWarehouses.some((warehouse) => warehouse.id === warehouseId)) setWarehouseId(undefined);
  }, [warehouseId, locationWarehouses]);
  const query = useQuery({
    queryKey: ["stock-opnames", page, search, status],
    queryFn: async () => (await stockOpnameApi.list({ page, page_size: PAGE_SIZE, search: search || undefined, status: status === "ALL" ? undefined : status })).data,
  });
  const create = useMutation({
    mutationFn: () => {
      if (!warehouseId) throw new Error("Warehouse is required");
      if (!locationId) throw new Error("Location is required");
      if (!departmentId) throw new Error("Department is required");
      return stockOpnameApi.create({ warehouse_id: warehouseId, location_id: locationId, department_id: departmentId, notes: notes || undefined });
    },
    onSuccess: async (r) => {
      await qc.invalidateQueries({ queryKey: ["stock-opnames"] });
      setShow(false); setWarehouseId(undefined); setLocationId(undefined); setDepartmentId(undefined); setNotes("");
      navigate(`/stock-opnames/${r.data.id}`);
    },
  });
  const data = query.data;
  const rows = data?.items ?? [];
  const locationOptions=(locations.data??[]).filter((location)=>location.is_active).map((location)=>({id:location.id,label:`${location.code} — ${location.name}`,keywords:[location.code??"",location.name??""]}));
  const warehouseOptions=locationWarehouses.map((warehouse)=>({id:warehouse.id,label:`${warehouse.code} — ${warehouse.name}`,keywords:[warehouse.code??"",warehouse.name??""]}));
  return (
    <DataWorkspace area="Inventory" className="inventory-print-report ">
<InventoryReportHeading title="Stock Opname" context={`Search: ${search || "All"} · Status: ${status}`} rows={rows.length} total={data?.total_items ?? 0}/>
      <PageHeader title="Stock Opname" description="Physical inventory count, variance approval, and controlled stock adjustment." actions={<>
<Button onClick={() => setShow(true)}>Create Stock Opname</Button>
<InventoryPrintButton loadReport={() => inventoryDocumentReport("opnames",{status:status === "ALL" ? undefined : status,search:search || undefined}, `Search: ${search || "All"} · Status: ${status}`)}/>
</>} />
      <Card className="p-2 print:hidden"><div className="flex gap-2"><input className={input} placeholder="Search opname number" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} /><Button variant="outline" title="Filters" aria-label="Filters" aria-expanded={showFilters} onClick={() => setShowFilters(v => !v)}><SlidersHorizontal size={15}/></Button></div>{showFilters && <div className="mt-2 max-w-xs"><select aria-label="Status" className={input} value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}>{["ALL","DRAFT","PENDING_APPROVAL","APPROVED","POSTED","REJECTED"].map((v) => <option key={v}>{v}</option>)}</select></div>}</Card>
      <Card className="workspace-data p-0"><div className="workspace-table-scroll overflow-x-auto"><table className="w-full min-w-[900px] text-xs"><thead><tr><th className="px-2 py-1.5 text-left">Number</th><th className="px-2 py-1.5 text-left">Count Date</th><th className="px-2 py-1.5 text-left">Warehouse</th><th className="px-2 py-1.5 text-left">Location</th><th className="px-2 py-1.5 text-right">Items</th>{data && !(data.blind_count ?? data.items.some(row=>row.blind_count)) && <th className="px-2 py-1.5 text-right">Variance</th>}<th className="px-2 py-1.5 text-left">Status</th></tr></thead><tbody>{rows.map((row) => <tr key={row.id} className="border-t whitespace-nowrap"><td className="px-2 py-1.5 font-medium"><Link className="text-emerald-700 hover:underline" to={`/stock-opnames/${row.id}`}>{row.opname_number}</Link></td><td className="px-2 py-1.5">{row.count_date}</td><td className="px-2 py-1.5">{row.warehouse_name ?? "—"}</td><td className="px-2 py-1.5">{row.location_name ?? "—"}</td><td className="px-2 py-1.5 text-right">{row.total_items}</td>{!(data?.blind_count ?? row.blind_count) && <td className="px-2 py-1.5 text-right">{Number(row.total_variance_quantity || 0).toLocaleString("id-ID")}</td>}<td className="px-2 py-1.5">{row.status.replaceAll("_", " ")}</td></tr>)}</tbody></table></div><div className="p-4 print:hidden"><Pagination page={page} pages={Math.max(data?.total_pages ?? 0, 1)} total={data?.total_items ?? 0} pageSize={PAGE_SIZE} noun="stock opnames" onChange={setPage} /></div></Card>
      {show && <div className="fixed inset-0 z-[80] grid place-items-center bg-black/40 p-4"><div className="w-full max-w-lg rounded-xl bg-white p-6"><h2 className="text-lg font-semibold">Create Stock Opname</h2><p className="mb-5 text-xs text-slate-500">Inventory quantities and average costs are snapshotted when this document is created. Business Unit is resolved automatically from the selected Location.</p><div className="space-y-3"><SearchableSelect label="Location" required value={locationId} disabled={locations.isLoading} placeholder="Type location code or name..." options={locationOptions} onChange={(value)=>{setLocationId(value);setWarehouseId(undefined);setDepartmentId(undefined)}}/><SearchableSelect label="Department" required value={departmentId} disabled={!locationId || departments.isLoading} options={(departments.data??[]).map(row=>({id:row.id,label:`${row.code} — ${row.name}`}))} onChange={setDepartmentId}/><SearchableSelect label="Warehouse" required value={warehouseId} disabled={!locationId || warehouses.isLoading} placeholder="Type warehouse code or name..." options={warehouseOptions} onChange={(value)=>setWarehouseId(value)}/></div><textarea className="mt-3 min-h-20 w-full rounded-md border p-3 text-sm" placeholder="Notes" value={notes} onChange={(e) => setNotes(e.target.value)} />{create.error && <div className="mt-2 text-sm text-red-600">{(() => { if (axios.isAxiosError(create.error)) { const detail=create.error.response?.data?.detail; const payload=detail&&typeof detail==="object"?detail:null; return <div><p>{payload?.message || (typeof detail==="string" ? detail : create.error.message)}</p>{payload?.opname_id && <Link className="font-medium underline" to={`/stock-opnames/${payload.opname_id}`}>Open {payload.opname_number ?? "active Stock Opname"}</Link>}</div>; } return create.error instanceof Error ? create.error.message : "Unable to create"; })()}</div>}<div className="mt-5 flex justify-end gap-2"><Button variant="secondary" onClick={() => {setShow(false);setWarehouseId(undefined);setLocationId(undefined);setDepartmentId(undefined);setNotes("")}}>Cancel</Button><Button disabled={create.isPending || !warehouseId || !locationId || !departmentId} onClick={() => create.mutate()}>Create</Button></div></div></div>}
    </DataWorkspace>
  );
}
