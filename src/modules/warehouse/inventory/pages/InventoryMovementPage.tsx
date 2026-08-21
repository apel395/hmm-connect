import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { TABLE_UI } from "@/config/tableUi";
import { useInventoryMovements } from "../useInventoryMovement";

const money=(value:unknown)=>Number(value??0).toLocaleString("id-ID",{minimumFractionDigits:2,maximumFractionDigits:2});
const input="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
const PAGE_SIZE=50;

export default function InventoryMovementPage(){
 const[params]=useSearchParams();
 const[productId,setProductId]=useState(params.get("product_id")??"");
 const[warehouseId,setWarehouseId]=useState(params.get("warehouse_id")??"");
 const[poId,setPoId]=useState(params.get("purchase_order_id")??"");
 const[receiptId,setReceiptId]=useState(params.get("goods_receipt_id")??"");
 const[locationId,setLocationId]=useState(params.get("location_id")??"");
 const[departmentId,setDepartmentId]=useState(params.get("department_id")??"");
 const[search,setSearch]=useState("");const[page,setPage]=useState(1);
 const filters=useMemo(()=>({product_id:productId?Number(productId):undefined,warehouse_id:warehouseId?Number(warehouseId):undefined,purchase_order_id:poId?Number(poId):undefined,goods_receipt_id:receiptId?Number(receiptId):undefined,location_id:locationId?Number(locationId):undefined,department_id:departmentId?Number(departmentId):undefined,search:search.trim()||undefined,page,page_size:PAGE_SIZE}),[productId,warehouseId,poId,receiptId,locationId,departmentId,search,page]);
 const query=useInventoryMovements(filters);const result=query.data;const rows=result?.items??[];const pages=Math.max(result?.total_pages??0,1);const total=result?.total_items??0;
 useEffect(()=>setPage(1),[productId,warehouseId,poId,receiptId,locationId,departmentId,search]);useEffect(()=>{if(page>pages)setPage(pages)},[page,pages]);
 if(query.isLoading)return <Loading/>;
 const pageValue=rows.reduce((sum,row)=>sum+Number(row.movement_value||0),0);
 const numeric=(setter:(value:string)=>void)=>(e:React.ChangeEvent<HTMLInputElement>)=>setter(e.target.value.replace(/\D/g,""));
 return <div className="space-y-6">
  <PageHeader title="Inventory Movement" description="Trace every posted stock movement back to Receiving, Purchase Order, warehouse, location and department."/>
  <Card className="p-4"><div className="mb-3"><input className={input} placeholder="Search item code, item name or warehouse..." value={search} onChange={e=>setSearch(e.target.value)}/></div><div className="grid gap-3 md:grid-cols-3 xl:grid-cols-6"><label className="text-xs font-medium text-slate-600">Product ID<input className={input} inputMode="numeric" value={productId} onChange={numeric(setProductId)} placeholder="All items"/></label><label className="text-xs font-medium text-slate-600">Warehouse ID<input className={input} inputMode="numeric" value={warehouseId} onChange={numeric(setWarehouseId)} placeholder="All warehouses"/></label><label className="text-xs font-medium text-slate-600">PO ID<input className={input} inputMode="numeric" value={poId} onChange={numeric(setPoId)} placeholder="All PO"/></label><label className="text-xs font-medium text-slate-600">Receiving ID<input className={input} inputMode="numeric" value={receiptId} onChange={numeric(setReceiptId)} placeholder="All RR"/></label><label className="text-xs font-medium text-slate-600">Location ID<input className={input} inputMode="numeric" value={locationId} onChange={numeric(setLocationId)} placeholder="All locations"/></label><label className="text-xs font-medium text-slate-600">Department ID<input className={input} inputMode="numeric" value={departmentId} onChange={numeric(setDepartmentId)} placeholder="All departments"/></label></div></Card>
  <div className="grid gap-3 md:grid-cols-3"><Card className="p-4"><div className="text-xs uppercase text-slate-500">Matching Movements</div><div className="mt-1 text-2xl font-bold">{total}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Current Page Value</div><div className="mt-1 text-2xl font-bold">Rp {money(pageValue)}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Traceability</div><div className="mt-1 text-sm font-medium">RR → PO → Site → Department</div></Card></div>
  <Card className="overflow-hidden p-0"><Table className="min-w-[1100px]" containerClassName="rounded-none border-0 shadow-none"><THead><TR className="whitespace-nowrap"><TH>Date</TH><TH>Movement</TH><TH>Product</TH><TH>Storage</TH><TH numeric>Qty</TH><TH numeric>Unit Cost</TH><TH numeric>Value</TH><TH>Source Documents</TH><TH>Notes</TH></TR></THead><TBody>{!rows.length?<TR><TD colSpan={9} className="p-10 text-center text-slate-500">No inventory movements match the selected filters.</TD></TR>:rows.map(row=><TR key={row.id} className="whitespace-nowrap"><TD>{new Date(row.movement_date).toLocaleString()}</TD><TD><TableCellStack primary={row.movement_number} secondary={<Badge variant={Number(row.quantity)>=0?"success":"danger"}>{row.movement_type}</Badge>}/></TD><TD className="max-w-[240px]"><TableCellStack primary={row.product_name} secondary={row.product_code}/></TD><TD><TableCellStack primary={row.warehouse_name} secondary={[row.location_id && `Location ${row.location_id}`, row.department_id && `Department ${row.department_id}`].filter(Boolean).join(" · ")}/></TD><TD numeric className="font-semibold">{Number(row.quantity).toLocaleString("id-ID")}</TD><TD numeric>{money(row.unit_cost)}</TD><TD numeric className="font-medium">{money(row.movement_value)}</TD><TD><div className="flex flex-col gap-0.5">{row.goods_receipt_id?<Link className={TABLE_UI.documentLink} to={`/receiving/${row.goods_receipt_id}`}>{row.receipt_number??`RR #${row.goods_receipt_id}`}</Link>:null}{row.purchase_order_id?<Link className={TABLE_UI.documentLink} to={`/purchase-orders/${row.purchase_order_id}`}>{row.purchase_order_number??`PO #${row.purchase_order_id}`}</Link>:null}{!row.goods_receipt_id&&!row.purchase_order_id?"—":null}</div></TD><TD className="max-w-[240px]"><span className="block truncate" title={row.notes??row.reference_number??undefined}>{row.notes??row.reference_number??"—"}</span></TD></TR>)}</TBody></Table><div className="p-4"><Pagination page={page} pages={pages} total={total} pageSize={PAGE_SIZE} noun="movements" onChange={setPage}/></div></Card>
 </div>;
}
