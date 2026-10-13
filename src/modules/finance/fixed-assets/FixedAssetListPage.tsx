import { filterBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import {Calculator, FileBarChart, FolderTree, Plus, Printer, Search, SlidersHorizontal, X} from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { TABLE_UI } from "@/config/tableUi";
import { listAssets, listCategories, syncInvoiceAssets } from "./api";

const money = (value: unknown) => value === null || value === undefined ? "—" : Number(value).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const blankFilters = { status: "", category_id: "", business_unit_id: "", location_id: "", department_id: "", date_from: "", date_to: "" };
const input = "h-9 rounded border px-2 text-sm";

export default function FixedAssetListPage() {
  const [page, setPage] = useState(1);
  const [pageSize,setPageSize] = useState(50);
  const [search,setSearch] = useState("");
  const [term,setTerm] = useState("");
  const [showFilters,setShowFilters] = useState(false);
  const [filters,setFilters] = useState({...blankFilters});
  useEffect(()=>{const timer=setTimeout(()=>{setTerm(search.trim());setPage(1);},300);return ()=>clearTimeout(timer);},[search]);
  const categories=useQuery({queryKey:["asset-categories"],queryFn:listCategories});
  const units=useQuery({queryKey:["asset-filter-units"],queryFn:()=>filterBusinessUnits({is_active:true})});
  const locations=useQuery({queryKey:["asset-filter-locations",filters.business_unit_id],queryFn:()=>listLocations({business_unit_id:Number(filters.business_unit_id)||undefined,is_active:true})});
  const departments=useQuery({queryKey:["asset-filter-departments",filters.business_unit_id,filters.location_id],queryFn:()=>listDepartments({business_unit_id:Number(filters.business_unit_id)||undefined,location_id:Number(filters.location_id)||undefined,is_active:true})});
  const setFilter=(key:keyof typeof blankFilters,value:string)=>{setFilters(current=>({...current,[key]:value,...(key==="business_unit_id"?{location_id:"",department_id:""}:key==="location_id"?{department_id:""}:{})}));setPage(1);};
  const activeFilters=Object.values(filters).filter(Boolean).length;
  const invalidDates=Boolean(filters.date_from&&filters.date_to&&filters.date_from>filters.date_to);
  const sync = useQuery({ queryKey: ["fixed-assets-source-sync"], queryFn: syncInvoiceAssets, refetchOnMount: "always" });
  const assets = useQuery({
    queryKey: ["fixed-assets", page, pageSize, term, filters],
    queryFn: () => listAssets({ page, page_size: pageSize, search: term || undefined, ...Object.fromEntries(Object.entries(filters).filter(([,value])=>Boolean(value))) }),
    enabled: !sync.isLoading && !invalidDates,
    placeholderData: (previousData) => previousData,
  });
  const rows = assets.data?.items ?? [];
  const total = assets.data?.total_items ?? 0;
  const pages = Math.max(assets.data?.total_pages ?? 0, 1);

  return <div className="space-y-5">
    <PageHeader
      title="Fixed Assets"
      description="Manage tangible assets, depreciation, and amortizable costs from one finance workspace."
      actions={<>
<Link to="/fixed-assets/new"><Button><Plus size={16}/> New Fixed Asset</Button></Link>
<Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</>}
    />

    <div className="grid gap-3 md:grid-cols-4">
      <Link to="/asset-categories"><Card className="h-full p-4 hover:border-emerald-300"><FolderTree className="mb-2 h-5 w-5 text-emerald-700"/><div className="font-semibold">Asset Categories</div><div className="mt-1 text-xs text-slate-500">Accounts and useful-life defaults</div></Card></Link>
      <Link to="/depreciation-runs"><Card className="h-full p-4 hover:border-emerald-300"><Calculator className="mb-2 h-5 w-5 text-emerald-700"/><div className="font-semibold">Depreciation Runs</div><div className="mt-1 text-xs text-slate-500">Calculate and post tangible-asset depreciation</div></Card></Link>
      <Link to="/fixed-assets/amortization"><Card className="h-full p-4 hover:border-emerald-300"><Calculator className="mb-2 h-5 w-5 text-emerald-700"/><div className="font-semibold">Amortization</div><div className="mt-1 text-xs text-slate-500">Intangible assets and amortizable costs</div></Card></Link>
      <Link to="/reports/fixed-assets"><Card className="h-full p-4 hover:border-emerald-300"><FileBarChart className="mb-2 h-5 w-5 text-emerald-700"/><div className="font-semibold">Asset Reports</div><div className="mt-1 text-xs text-slate-500">Book value and depreciation reporting</div></Card></Link>
    </div>

    {sync.isError && <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">Invoice asset registration could not be synchronized. Refresh after the backend is updated.</div>}
    <div className="flex items-center gap-2 print:hidden"><Search size={16}/><input aria-label="Search assets" placeholder="Asset name, number, item code, serial or barcode" className={`${input} min-w-0 flex-1`} value={search} onChange={e=>setSearch(e.target.value)}/><Button variant="outline" aria-label="Asset filters" title="Filters" onClick={()=>setShowFilters(!showFilters)}><SlidersHorizontal size={16}/>{activeFilters||null}</Button><select aria-label="Assets per page" className={input} value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setPage(1);}}>{[20,50,100,200].map(size=><option key={size} value={size}>{size} / page</option>)}</select>{(activeFilters||search)&&<Button variant="outline" title="Clear search and filters" aria-label="Clear search and filters" onClick={()=>{setFilters({...blankFilters});setSearch("");setTerm("");setPage(1);}}><X size={16}/></Button>}</div>
    {showFilters&&<Card className="grid gap-2 p-3 text-sm md:grid-cols-4 print:hidden">
      <label>Status<select className={`${input} block w-full`} value={filters.status} onChange={e=>setFilter("status",e.target.value)}><option value="">All statuses</option>{["PENDING_REGISTRATION","PENDING_SETUP","DRAFT","ACTIVE","FULLY_DEPRECIATED","DISPOSED","WRITTEN_OFF","INACTIVE"].map(status=><option key={status} value={status}>{status.replaceAll("_"," ")}</option>)}</select></label>
      <label>Category<select className={`${input} block w-full`} value={filters.category_id} onChange={e=>setFilter("category_id",e.target.value)}><option value="">All categories</option>{categories.data?.map((c:any)=><option key={c.id} value={c.id}>{c.name}</option>)}</select></label>
      <label>Business Unit<select className={`${input} block w-full`} value={filters.business_unit_id} onChange={e=>setFilter("business_unit_id",e.target.value)}><option value="">All accessible units</option>{units.data?.map(u=><option key={u.id} value={u.id}>{u.name}</option>)}</select></label>
      <label>Location<select className={`${input} block w-full`} value={filters.location_id} onChange={e=>setFilter("location_id",e.target.value)}><option value="">All accessible locations</option>{locations.data?.map(l=><option key={l.id} value={l.id}>{l.name}</option>)}</select></label>
      <label>Department<select className={`${input} block w-full`} value={filters.department_id} onChange={e=>setFilter("department_id",e.target.value)}><option value="">All accessible departments</option>{departments.data?.map(d=><option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
      <label>Acquired From<input type="date" className={`${input} block w-full`} value={filters.date_from} onChange={e=>setFilter("date_from",e.target.value)}/></label>
      <label>Acquired To<input type="date" className={`${input} block w-full`} value={filters.date_to} onChange={e=>setFilter("date_to",e.target.value)}/></label>
    </Card>}
    {invalidDates&&<p role="alert" className="text-sm text-red-700">From date must be before To date.</p>}
    {assets.isError&&<p role="alert" className="text-sm text-red-700">Assets could not be loaded.</p>}
    <Card className="overflow-x-auto p-0">
      <div className="border-b px-4 py-3 font-semibold">Asset Register</div>
      <Table className={`min-w-[900px] ${assets.isFetching ? "opacity-70" : ""}`} containerClassName="rounded-none border-0 shadow-none">
        <THead><TR className="whitespace-nowrap"><TH>Asset</TH><TH numeric>Quantity</TH><TH>Acquired</TH><TH numeric>Cost</TH><TH numeric>Accumulated Depreciation</TH><TH numeric>Net Book Value</TH><TH>Status</TH><TH numeric>Action</TH></TR></THead>
        <TBody>{rows.map((asset: any) => <TR key={asset.id} className="whitespace-nowrap"><TD><TableCellStack primary={asset.asset_name} secondary={`${asset.asset_number} · ${asset.category || "Category setup required"}`}/></TD><TD numeric>{asset.quantity ?? "—"}</TD><TD>{asset.acquisition_date || "—"}</TD><TD numeric>{money(asset.acquisition_cost)}</TD><TD numeric>{money(asset.accumulated_depreciation)}</TD><TD numeric className="font-semibold">{money(asset.net_book_value)}</TD><TD><Badge>{asset.status}</Badge></TD><TD><div className="flex justify-end"><Link className={TABLE_UI.documentLink} to={asset.status === "PENDING_REGISTRATION" ? `/fixed-assets/new?registration_id=${asset.id}` : `/fixed-assets/${asset.id}`}>{asset.status === "PENDING_REGISTRATION" ? "Complete" : "View"}</Link></div></TD></TR>)}</TBody>
      </Table>
      {!assets.isLoading && !rows.length && <div className="p-10 text-center text-sm text-slate-500">No fixed assets registered.</div>}
      {!assets.isLoading && total > 0 && <div className="border-t px-4 py-3"><Pagination page={page} pages={pages} total={total} pageSize={pageSize} noun="assets" onChange={setPage}/></div>}
    </Card>
  </div>;
}
