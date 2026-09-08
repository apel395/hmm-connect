import { useEffect, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { Printer } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import InventoryTable from "../components/InventoryTable";
import { useInventory } from "../useInventory";

const money=(value:unknown)=>Number(value??0).toLocaleString("id-ID",{minimumFractionDigits:2,maximumFractionDigits:2});
const input="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const PAGE_SIZE=25;
type HealthFilter="ALL"|"HEALTHY"|"LOW_STOCK";

export default function InventoryPage(){
 const[params,setParams]=useSearchParams();
 const initialHealth=params.get("health")==="LOW_STOCK"?"LOW_STOCK":params.get("health")==="HEALTHY"?"HEALTHY":"ALL";
 const[search,setSearch]=useState("");
 const[health,setHealth]=useState<HealthFilter>(initialHealth);
 const[page,setPage]=useState(1);
 const query=useInventory({page,page_size:PAGE_SIZE,search:search.trim()||undefined,health:health==="ALL"?undefined:health});
 const data:any=query.data??{};const rows:any[]=data.items??[];const summary=data.summary??{};const pages=Math.max(data.total_pages??0,1);const total=data.total_items??0;
 useEffect(()=>setPage(1),[search,health]);useEffect(()=>{if(page>pages)setPage(pages)},[page,pages]);
 const changeHealth=(value:HealthFilter)=>{setHealth(value);const next=new URLSearchParams(params);if(value==="ALL")next.delete("health");else next.set("health",value);setParams(next,{replace:true})};
  return <div className="space-y-6">
   <div className="hidden print:block"><h1 className="text-2xl font-bold">MMH-Connect</h1><h2 className="text-xl font-semibold">Inventory</h2><p className="text-xs text-slate-500">Printed {new Date().toLocaleString()}</p></div>
   <div className="print:hidden"><PageHeader title="Inventory" description="Current warehouse stock and valuation. Minimum stock alerts are evaluated per warehouse from Item Master thresholds." actions={<Button variant="outline" onClick={() => window.print()}><Printer size={16} /> Print</Button>} /></div>
   <div className="hidden print:block"><PageHeader title="Inventory" description="Current warehouse stock and valuation." /></div>
  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3"><Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Stock Lines</div><div className="mt-2 text-2xl font-bold">{summary.stock_lines??0}</div></Card><Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Stock Value</div><div className="mt-2 text-2xl font-bold">Rp {money(summary.stock_value)}</div></Card><Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Reorder Required</div><div className="mt-2 text-2xl font-bold text-red-700">{summary.low_stock??0}</div><div className="mt-1 text-xs text-slate-500">Warehouse-item lines at or below minimum</div></Card></div>
  <Card className="p-4"><div className="grid gap-3 md:grid-cols-[1fr_240px]"><input className={input} placeholder="Search item code, name or warehouse" value={search} onChange={e=>setSearch(e.target.value)}/><select className={input} value={health} onChange={e=>changeHealth(e.target.value as HealthFilter)}><option value="ALL">All stock</option><option value="HEALTHY">Healthy</option><option value="LOW_STOCK">Low Stock / Reorder Required</option></select></div></Card>
  <Card className="p-0">{query.isLoading?<Loading/>:<><InventoryTable rows={rows}/><div className="p-4"><Pagination page={page} pages={pages} total={total} pageSize={PAGE_SIZE} noun="stock lines" onChange={setPage}/></div></>}</Card>
 </div>;
}
