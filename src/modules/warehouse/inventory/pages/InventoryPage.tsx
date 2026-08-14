import { useMemo, useState } from "react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import InventoryTable from "../components/InventoryTable";
import { useInventory } from "../useInventory";

const money=(value:unknown)=>Number(value??0).toLocaleString("id-ID",{minimumFractionDigits:2,maximumFractionDigits:2});
const input="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

export default function InventoryPage(){
 const{data=[],isLoading}=useInventory();
 const[search,setSearch]=useState("");
 const[health,setHealth]=useState<"ALL"|"HEALTHY"|"REORDER"|"BELOW_MINIMUM">("ALL");
 const filtered=useMemo(()=>data.filter((row:any)=>{
   const term=search.trim().toLowerCase();
   const matches=!term||row.product_code?.toLowerCase().includes(term)||row.product_name?.toLowerCase().includes(term)||row.warehouse_name?.toLowerCase().includes(term);
   const healthMatch=health==="ALL"||(health==="BELOW_MINIMUM"&&row.below_minimum)||(health==="REORDER"&&row.needs_reorder&&!row.below_minimum)||(health==="HEALTHY"&&!row.needs_reorder&&!row.below_minimum);
   return matches&&healthMatch;
 }),[data,search,health]);
 const totalValue=data.reduce((sum:any,row:any)=>sum+Number(row.stock_value||0),0);
 const reorderCount=data.filter((row:any)=>row.needs_reorder).length;
 const belowMinimumCount=data.filter((row:any)=>row.below_minimum).length;
 const stockLines=data.length;
 return <div className="space-y-6">
  <PageHeader title="Inventory" description="Current warehouse stock, valuation and replenishment health."/>
  <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Stock Lines</div><div className="mt-2 text-2xl font-bold">{stockLines}</div></Card><Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Stock Value</div><div className="mt-2 text-2xl font-bold">Rp {money(totalValue)}</div></Card><Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Need Reorder</div><div className="mt-2 text-2xl font-bold text-amber-700">{reorderCount}</div></Card><Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">Below Minimum</div><div className="mt-2 text-2xl font-bold text-red-700">{belowMinimumCount}</div></Card></div>
  <Card className="p-4"><div className="grid gap-3 md:grid-cols-[1fr_240px]"><input className={input} placeholder="Search item code, name or warehouse" value={search} onChange={e=>setSearch(e.target.value)}/><select className={input} value={health} onChange={e=>setHealth(e.target.value as any)}><option value="ALL">All stock health</option><option value="HEALTHY">Healthy</option><option value="REORDER">Reorder</option><option value="BELOW_MINIMUM">Below Minimum</option></select></div></Card>
  <Card className="p-0">{isLoading?<Loading/>:<InventoryTable rows={filtered}/>}</Card>
 </div>;
}
