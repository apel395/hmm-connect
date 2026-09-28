import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import PageHeader from "@/components/common/PageHeader";
import { Printer } from "lucide-react";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Pagination from "@/components/datatable/Pagination";
import Loading from "@/components/ui/Loading";
import { useInventoryMovements } from "@/modules/warehouse/inventory/useInventoryMovement";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";

const input = "h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const num = (v: unknown) => Number(v ?? 0).toLocaleString("id-ID");
const money = (v: unknown) => Number(v ?? 0).toLocaleString("id-ID", {minimumFractionDigits: 2, maximumFractionDigits: 2});

export default function StockCardPage() {
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [accountId, setAccountId] = useState("");
  const [productId, setProductId] = useState("");
  const [warehouseId, setWarehouseId] = useState("");
  const [page, setPage] = useState(1);
  const accounts = useQuery({queryKey:["stock-card-coa"],queryFn:()=>getAllAccountLookup({is_active:true,is_posting:true})});
  const query = useInventoryMovements({
    date_from:dateFrom||undefined, date_to:dateTo||undefined,
    account_id:accountId?Number(accountId):undefined,
    product_id:productId?Number(productId):undefined,
    warehouse_id:warehouseId?Number(warehouseId):undefined,
    page, page_size:50,
  });
  const data = query.data;
  return <div className="space-y-6">
    <PageHeader actions={<Button variant="outline" onClick={()=>window.print()}><Printer size={16}/> Print</Button>} title="Stock Card" description="Inventory movements and totals for the selected date range and account."/>
    <Card className="p-4"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
      <label className="text-xs font-medium text-slate-600">From date<input type="date" className={input} value={dateFrom} onChange={e=>{setDateFrom(e.target.value);setPage(1)}}/></label>
      <label className="text-xs font-medium text-slate-600">To date<input type="date" min={dateFrom||undefined} className={input} value={dateTo} onChange={e=>{setDateTo(e.target.value);setPage(1)}}/></label>
      <label className="text-xs font-medium text-slate-600">Inventory account<select className={input} value={accountId} onChange={e=>{setAccountId(e.target.value);setPage(1)}}><option value="">All inventory COA</option>{(accounts.data??[]).map((a:any)=><option key={a.id} value={a.id}>{a.account_number} — {a.account_name}</option>)}</select></label>
      <label className="text-xs font-medium text-slate-600">Product ID<input type="number" min="1" className={input} value={productId} onChange={e=>{setProductId(e.target.value);setPage(1)}} placeholder="All products"/></label>
      <label className="text-xs font-medium text-slate-600">Warehouse ID<input type="number" min="1" className={input} value={warehouseId} onChange={e=>{setWarehouseId(e.target.value);setPage(1)}} placeholder="All warehouses"/></label>
    </div></Card>
    {query.isLoading?<Loading/>:<>
      <Card className="p-0"><div className="border-b px-4 py-3 font-semibold">Full Period Totals by Inventory Account</div><div className="overflow-x-auto"><table className="w-full min-w-[780px] text-sm"><thead><tr><th className="px-4 py-2 text-left">Account</th><th className="px-4 py-2 text-right">IN Qty</th><th className="px-4 py-2 text-right">OUT Qty</th><th className="px-4 py-2 text-right">Net Qty</th><th className="px-4 py-2 text-right">IN Value</th><th className="px-4 py-2 text-right">OUT Value</th><th className="px-4 py-2 text-right">Net Value</th></tr></thead><tbody>{(data?.totals_by_account??[]).map(a=><tr key={a.account_id??"none"} className="border-t"><td className="px-4 py-2">{a.account_code? `${a.account_code} — ${a.account_name}`:"Unmapped"}</td><td className="px-4 py-2 text-right">{num(a.in_qty)}</td><td className="px-4 py-2 text-right">{num(a.out_qty)}</td><td className="px-4 py-2 text-right">{num(a.net_qty)}</td><td className="px-4 py-2 text-right">Rp {money(a.in_value)}</td><td className="px-4 py-2 text-right">Rp {money(a.out_value)}</td><td className="px-4 py-2 text-right">Rp {money(a.net_value)}</td></tr>)}{!data?.totals_by_account?.length&&<tr><td colSpan={7} className="p-6 text-center text-slate-500">No movements for the selected dates.</td></tr>}</tbody></table></div></Card>
      <Card className="p-0"><div className="border-b px-4 py-3 font-semibold">Transactions ({num(data?.total_items)})</div><div className="overflow-x-auto"><table className="w-full min-w-[840px] text-sm"><thead><tr><th className="px-4 py-2 text-left">Date</th><th className="px-4 py-2 text-left">Reference</th><th className="px-4 py-2 text-left">Product</th><th className="px-4 py-2 text-left">Account / Warehouse</th><th className="px-4 py-2 text-right">IN</th><th className="px-4 py-2 text-right">OUT</th><th className="px-4 py-2 text-right">Value</th></tr></thead><tbody>{(data?.items??[]).map(m=><tr key={m.id} className="border-t"><td className="px-4 py-2">{m.movement_date}</td><td className="px-4 py-2">{m.reference_number??m.movement_number}</td><td className="px-4 py-2">{m.product_code} — {m.product_name}</td><td className="px-4 py-2">{m.inventory_account_code??"Unmapped"} / {m.warehouse_name}</td><td className="px-4 py-2 text-right">{m.movement_type==="IN"?num(m.quantity):"—"}</td><td className="px-4 py-2 text-right">{m.movement_type==="OUT"?num(m.quantity):"—"}</td><td className="px-4 py-2 text-right">Rp {money(m.movement_value)}</td></tr>)}</tbody></table></div><div className="p-4"><Pagination page={page} pages={Math.max(data?.total_pages??0,1)} total={data?.total_items??0} pageSize={50} noun="movements" onChange={setPage}/></div></Card>
    </>}
  </div>;
}
