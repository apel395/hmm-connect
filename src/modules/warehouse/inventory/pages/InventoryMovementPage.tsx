import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Loading from "@/components/ui/Loading";
import { useInventoryMovements } from "../useInventoryMovement";

const money=(value:unknown)=>Number(value??0).toLocaleString("id-ID",{minimumFractionDigits:2,maximumFractionDigits:2});
const input="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";

export default function InventoryMovementPage(){
 const[poId,setPoId]=useState(""),[receiptId,setReceiptId]=useState(""),[locationId,setLocationId]=useState(""),[departmentId,setDepartmentId]=useState("");
 const filters=useMemo(()=>({purchase_order_id:poId?Number(poId):undefined,goods_receipt_id:receiptId?Number(receiptId):undefined,location_id:locationId?Number(locationId):undefined,department_id:departmentId?Number(departmentId):undefined}),[poId,receiptId,locationId,departmentId]);
 const{data=[],isLoading}=useInventoryMovements(filters);
 if(isLoading)return <Loading/>;
 const totalValue=data.reduce((sum,row)=>sum+Number(row.movement_value||0),0);
 return <div className="space-y-6">
  <PageHeader title="Inventory Movement" description="Trace every posted stock movement back to Receiving, Purchase Order, warehouse, location and department."/>
  <Card className="p-4"><div className="grid gap-3 md:grid-cols-4"><label className="text-xs font-medium text-slate-600">PO ID<input className={input} inputMode="numeric" value={poId} onChange={e=>setPoId(e.target.value.replace(/\D/g,""))} placeholder="All PO"/></label><label className="text-xs font-medium text-slate-600">Receiving ID<input className={input} inputMode="numeric" value={receiptId} onChange={e=>setReceiptId(e.target.value.replace(/\D/g,""))} placeholder="All RR"/></label><label className="text-xs font-medium text-slate-600">Location ID<input className={input} inputMode="numeric" value={locationId} onChange={e=>setLocationId(e.target.value.replace(/\D/g,""))} placeholder="All locations"/></label><label className="text-xs font-medium text-slate-600">Department ID<input className={input} inputMode="numeric" value={departmentId} onChange={e=>setDepartmentId(e.target.value.replace(/\D/g,""))} placeholder="All departments"/></label></div></Card>
  <div className="grid gap-3 md:grid-cols-3"><Card className="p-4"><div className="text-xs uppercase text-slate-500">Movements</div><div className="mt-1 text-2xl font-bold">{data.length}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Movement Value</div><div className="mt-1 text-2xl font-bold">Rp {money(totalValue)}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Traceability</div><div className="mt-1 text-sm font-medium">RR → PO → Site → Department</div></Card></div>
  <Card className="overflow-hidden p-0"><div className="overflow-x-auto"><table className="min-w-[1450px] w-full text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-left">Date</th><th>Movement</th><th>Product</th><th>Warehouse</th><th>Type</th><th className="text-right">Qty</th><th className="text-right">Unit Cost</th><th className="text-right">Value</th><th>Receiving</th><th>Purchase Order</th><th>Location</th><th>Department</th><th className="p-3 text-left">Notes</th></tr></thead><tbody>{!data.length?<tr><td colSpan={13} className="p-10 text-center text-slate-500">No inventory movements match the selected filters.</td></tr>:data.map(row=><tr key={row.id} className="border-t"><td className="p-3">{new Date(row.movement_date).toLocaleString()}</td><td className="font-medium">{row.movement_number}</td><td><div className="font-medium">{row.product_name}</div><div className="text-xs text-slate-500">{row.product_code}</div></td><td>{row.warehouse_name}</td><td><Badge variant={Number(row.quantity)>=0?"success":"danger"}>{row.movement_type}</Badge></td><td className="text-right font-medium">{Number(row.quantity).toLocaleString()}</td><td className="text-right">{money(row.unit_cost)}</td><td className="text-right font-medium">{money(row.movement_value)}</td><td>{row.goods_receipt_id?<Link className="text-emerald-700 hover:underline" to={`/receiving/${row.goods_receipt_id}`}>{row.receipt_number??`RR #${row.goods_receipt_id}`}</Link>:"—"}</td><td>{row.purchase_order_id?<Link className="text-emerald-700 hover:underline" to={`/purchase-orders/${row.purchase_order_id}`}>{row.purchase_order_number??`PO #${row.purchase_order_id}`}</Link>:"—"}</td><td>{row.location_id??"—"}</td><td>{row.department_id??"—"}</td><td className="p-3 text-slate-600">{row.notes??row.reference_number??"—"}</td></tr>)}</tbody></table></div></Card>
 </div>
}
