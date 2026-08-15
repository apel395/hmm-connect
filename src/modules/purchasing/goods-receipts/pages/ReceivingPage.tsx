import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import ListToolbar from "@/components/common/ListToolbar";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import ReceiveGoodsDialog from "../components/ReceiveGoodsDialog";
import DirectReceiveDialog from "../components/DirectReceiveDialog";
import { useAllGoodsReceipts, useReceivablePurchaseOrders } from "../hooks/useGoodsReceipts";
import useAuthorization from "@/hooks/useAuthorization";

const PAGE_SIZE=25;
const workflowStatus=(receipt:any)=>receipt.status==="POSTED"?"Posted":receipt.status==="RETURNED"?"Returned":receipt.approval_status==="APPROVED"?"Approved to Post":receipt.approval_status==="PENDING"?"Waiting Approval":receipt.approval_status==="REJECTED"?"Rejected":"Draft";
const workflowVariant=(receipt:any)=>receipt.status==="POSTED"?"success":receipt.approval_status==="APPROVED"?"success":receipt.approval_status==="PENDING"?"warning":receipt.approval_status==="REJECTED"?"danger":"outline";

function workflowParams(status:string){
  if(status==="Waiting Approval")return{approval_status:"PENDING"};
  if(status==="Approved to Post")return{status:"DRAFT",approval_status:"APPROVED"};
  if(status==="Posted")return{status:"POSTED"};
  if(status==="Rejected")return{approval_status:"REJECTED"};
  if(status==="Returned")return{status:"RETURNED"};
  if(status==="Draft")return{status:"DRAFT"};
  return{};
}

export default function ReceivingPage() {
  const navigate=useNavigate();const{canPerform}=useAuthorization();const canCreate=canPerform("receive",["WAREHOUSE","PURCHASING"]);
  const[search,setSearch]=useState("");const[destination,setDestination]=useState("ALL");const[status,setStatus]=useState("ALL");const[advanced,setAdvanced]=useState(false);const[creating,setCreating]=useState(false);const[direct,setDirect]=useState(false);const[page,setPage]=useState(1);
  const query=useAllGoodsReceipts({page,page_size:PAGE_SIZE,search:search.trim()||undefined,destination_type:destination==="ALL"?undefined:destination,...workflowParams(status)});const pending=useReceivablePurchaseOrders();const data:any=query.data??{};const rows:any[]=data.items??[];const summary=data.summary??{};const pages=Math.max(data.total_pages??0,1);const total=data.total_items??0;
  useEffect(()=>setPage(1),[search,destination,status]);useEffect(()=>{if(page>pages)setPage(pages)},[page,pages]);
  const destinationSelect=<select className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm" value={destination} onChange={(event)=>setDestination(event.target.value)}><option value="ALL">All destinations</option><option value="WAREHOUSE">Warehouse</option><option value="DIRECT_USE">Direct Use</option></select>;
  const statusSelect=<select className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm" value={status} onChange={(event)=>setStatus(event.target.value)}><option value="ALL">All workflow statuses</option>{["Draft","Waiting Approval","Approved to Post","Posted","Rejected","Returned"].map(value=><option key={value} value={value}>{value}</option>)}</select>;
  return <><div className="space-y-6"><PageHeader title="Receiving / RR" description="Create Receiving Reports, complete approval, then post approved receipts to inventory." actions={canCreate?<div className="flex gap-2"><Button variant="outline" onClick={()=>setDirect(true)}><Plus size={16}/> Direct RR</Button><Button onClick={()=>setCreating(true)}><Plus size={16}/> RR from PO</Button></div>:undefined}/><ModuleSummary metrics={[{label:"Receivable POs",value:(pending.data??[]).length},{label:"Waiting Approval",value:summary.waiting_approval??0},{label:"Approved to Post",value:summary.approved_to_post??0},{label:"Posted",value:summary.posted??0}]}/><Card className="overflow-hidden p-0"><div className="p-5"><ListToolbar search={search} searchPlaceholder="Search RR, PO, supplier, site, department, or warehouse..." onSearch={setSearch} filters={<div className="flex gap-2">{destinationSelect}{statusSelect}</div>} advancedOpen={advanced} onAdvancedToggle={()=>setAdvanced(!advanced)} advancedFilters={<div className="flex max-w-2xl gap-2">{destinationSelect}{statusSelect}</div>} onRefresh={()=>{query.refetch();pending.refetch()}} footer={<div className="text-xs text-slate-500">{total} Receiving Report{total===1?"":"s"} match current filters</div>}/></div>{query.isLoading?<div className="py-12"><Loading/></div>:query.isError?<div role="alert" className="m-5 rounded border border-red-200 bg-red-50 p-4 text-red-700">Receiving documents could not be loaded.</div>:<><div className="overflow-x-auto"><table className="min-w-[1450px] w-full text-sm"><thead><tr className="border-b bg-slate-50 text-left"><th className="p-3">RR Number</th><th>Source</th><th>PO Number</th><th>Supplier</th><th>Location</th><th>Department</th><th>Receipt Date</th><th>Destination</th><th>Warehouse</th><th>Workflow</th><th className="text-right">Total</th><th className="p-3 text-right">Action</th></tr></thead><tbody>{rows.map(receipt=><tr key={receipt.id} className="border-b hover:bg-slate-50"><td className="p-3 font-medium">{receipt.receipt_number}</td><td>{receipt.source_mode==="DIRECT"?"Direct":"PO"}</td><td>{receipt.purchase_order_number??"—"}</td><td>{receipt.supplier_name??"—"}</td><td>{receipt.location_name??"—"}</td><td>{receipt.department_name??"—"}</td><td>{new Date(receipt.received_at).toLocaleDateString()}</td><td>{receipt.destination_type==="WAREHOUSE"?"Warehouse":"Direct Use"}</td><td>{receipt.destination_type==="WAREHOUSE"?receipt.warehouse_name??"—":"—"}</td><td><Badge variant={workflowVariant(receipt) as any}>{workflowStatus(receipt)}</Badge></td><td className="text-right tabular-nums">{Number(receipt.total_amount??0).toLocaleString("id-ID",{minimumFractionDigits:2,maximumFractionDigits:2})}</td><td className="p-3 text-right"><Button size="sm" variant="outline" onClick={()=>navigate(`/receiving/${receipt.id}`)}>View</Button></td></tr>)}{!rows.length&&<tr><td colSpan={12} className="p-10 text-center text-slate-500">No Receiving Reports found.</td></tr>}</tbody></table></div><div className="p-5"><Pagination page={page} pages={pages} total={total} pageSize={PAGE_SIZE} noun="receiving reports" onChange={setPage}/></div></>}</Card></div>{canCreate&&<ReceiveGoodsDialog open={creating} purchaseOrder={null} onClose={()=>setCreating(false)}/>} {canCreate&&<DirectReceiveDialog open={direct} onClose={()=>setDirect(false)}/>}</>;
}
