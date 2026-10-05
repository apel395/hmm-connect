import { useEffect, useState } from "react";
import {Plus, Printer} from "lucide-react";
import axios from "axios";
import { toast } from "sonner";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import ListToolbar from "@/components/common/ListToolbar";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import DateRangeFilter from "@/components/common/DateRangeFilter";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import ReceiveGoodsDialog from "../components/ReceiveGoodsDialog";
import DirectReceiveDialog from "../components/DirectReceiveDialog";
import { useAllGoodsReceipts, useReceivablePurchaseOrders, useSubmitGoodsReceipt, usePostGoodsReceipt } from "../hooks/useGoodsReceipts";
import useAuthorization from "@/hooks/useAuthorization";

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
  const submitReceipt=useSubmitGoodsReceipt();const postReceipt=usePostGoodsReceipt();
  const actionError=(error:unknown)=>{const detail=axios.isAxiosError(error)?error.response?.data?.detail:null;toast.error(typeof detail==="string"?detail:"Receiving action failed")};
  const navigate=useNavigate();const{isSuperuser,hasPermission}=useAuthorization();const canCreate=isSuperuser()||hasPermission("receiving.create");
  const[search,setSearch]=useState("");const[destination,setDestination]=useState("ALL");const[status,setStatus]=useState("ALL");const[advanced,setAdvanced]=useState(false);const[creating,setCreating]=useState(false);const[direct,setDirect]=useState(false);const[page,setPage]=useState(1);const[pageSize,setPageSize]=useState(()=>Number(window.localStorage.getItem("receiving-page-size"))===100?100:50);const[dateFrom,setDateFrom]=useState("");const[dateTo,setDateTo]=useState("");const[appliedDateFrom,setAppliedDateFrom]=useState("");const[appliedDateTo,setAppliedDateTo]=useState("");
  const query=useAllGoodsReceipts({page,page_size:pageSize,search:search.trim()||undefined,destination_type:destination==="ALL"?undefined:destination,...workflowParams(status),date_from:appliedDateFrom||undefined,date_to:appliedDateTo||undefined});const pending=useReceivablePurchaseOrders();const data:any=query.data??{};const rows:any[]=data.items??[];const summary=data.summary??{};const pages=Math.max(data.total_pages??0,1);const total=data.total_items??0;
  useEffect(()=>setPage(1),[search,destination,status,appliedDateFrom,appliedDateTo,pageSize]);useEffect(()=>{if(page>pages)setPage(pages)},[page,pages]);
  useEffect(()=>window.localStorage.setItem("receiving-page-size",String(pageSize)),[pageSize]);
  const destinationSelect=<select className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm" value={destination} onChange={(event)=>setDestination(event.target.value)}><option value="ALL">All destinations</option><option value="WAREHOUSE">Warehouse</option><option value="DIRECT_USE">Direct Use</option></select>;
  const statusSelect=<select className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm" value={status} onChange={(event)=>setStatus(event.target.value)}><option value="ALL">All workflow statuses</option>{["Draft","Waiting Approval","Approved to Post","Posted","Rejected","Returned"].map(value=><option key={value} value={value}>{value}</option>)}</select>;
  const dateFilter=<DateRangeFilter from={dateFrom} to={dateTo} onFromChange={setDateFrom} onToChange={setDateTo} onApply={()=>{setAppliedDateFrom(dateFrom);setAppliedDateTo(dateTo)}} onClear={()=>{setDateFrom("");setDateTo("");setAppliedDateFrom("");setAppliedDateTo("")}}/>;
  return <><div className="space-y-6"><PageHeader title="Receiving / RR" description="Create Receiving Reports, complete approval, then post approved receipts to inventory." actions={canCreate?<div className="flex gap-2"><Button variant="outline" onClick={()=>setDirect(true)}><Plus size={16}/> Direct RR</Button><Button onClick={()=>setCreating(true)}><Plus size={16}/> RR from PO</Button>  <Button variant="outline" onClick={() => window.print()}><Printer size={16}/> Print</Button>
</div>:undefined}/><ModuleSummary metrics={[{label:"Receivable POs",value:(pending.data??[]).length},{label:"Waiting Approval",value:summary.waiting_approval??0},{label:"Approved to Post",value:summary.approved_to_post??0},{label:"Posted",value:summary.posted??0}]}/><Card className="overflow-hidden p-0"><div className="p-3"><ListToolbar search={search} searchPlaceholder="Search RR, PO, supplier, site, department, or warehouse..." onSearch={setSearch} filters={<div className="flex gap-2">{destinationSelect}{statusSelect}</div>} advancedOpen={advanced} onAdvancedToggle={()=>setAdvanced(!advanced)} advancedFilters={<div className="space-y-3"><div className="flex gap-2">{destinationSelect}{statusSelect}</div>{dateFilter}</div>} onRefresh={()=>{query.refetch();pending.refetch()}} footer={<div className="text-xs text-slate-500">{total} Receiving Report{total===1?"":"s"} match current filters</div>}/></div>{query.isLoading?<div className="py-12"><Loading/></div>:query.isError?<div role="alert" className="m-5 rounded border border-red-200 bg-red-50 p-4 text-red-700">Receiving documents could not be loaded.</div>:<><Table className="min-w-[950px]" containerClassName="rounded-none border-x-0 shadow-none"><THead><TR className="whitespace-nowrap"><TH>Receiving Report</TH><TH>Source Document</TH><TH>Organization</TH><TH>Destination</TH><TH>Workflow</TH><TH numeric>Total</TH><TH numeric>Action</TH></TR></THead><TBody>{rows.map(receipt=><TR key={receipt.id} className="whitespace-nowrap"><TD><TableCellStack primary={receipt.receipt_number} secondary={new Date(receipt.received_at).toLocaleDateString()}/></TD><TD><TableCellStack primary={receipt.purchase_order_number??(receipt.source_mode==="DIRECT"?"Direct Receiving":"—")} secondary={receipt.supplier_name??undefined}/></TD><TD>{receipt.location_name||receipt.department_name?<TableCellStack primary={receipt.location_name||receipt.department_name} secondary={receipt.location_name?receipt.department_name:undefined}/>:"—"}</TD><TD><TableCellStack primary={receipt.destination_type==="WAREHOUSE"?"Warehouse":"Direct Use"} secondary={receipt.destination_type==="WAREHOUSE"?receipt.warehouse_name??undefined:undefined}/></TD><TD><Badge variant={workflowVariant(receipt) as any}>{workflowStatus(receipt)}</Badge></TD><TD numeric className="font-semibold">{Number(receipt.total_amount??0).toLocaleString("id-ID",{minimumFractionDigits:2,maximumFractionDigits:2})}</TD><TD><div className="flex justify-end gap-1">{receipt.allowed_actions?.can_submit&&<Button size="sm" loading={submitReceipt.isPending} onClick={()=>submitReceipt.mutate(receipt.id,{onSuccess:()=>toast.success("Receiving submitted"),onError:actionError})}>Submit</Button>}{receipt.allowed_actions?.can_post&&<Button size="sm" loading={postReceipt.isPending} onClick={()=>postReceipt.mutate(receipt.id,{onSuccess:()=>toast.success("Receiving posted"),onError:actionError})}>Post</Button>}<Button size="sm" variant="outline" onClick={()=>navigate(`/receiving/${receipt.id}`)}>View</Button></div></TD></TR>)}{!rows.length&&<TR><TD colSpan={7} className="p-10 text-center text-slate-500">No Receiving Reports found.</TD></TR>}</TBody></Table><div className="flex flex-wrap items-center justify-between gap-2 px-3 py-2"><label className="text-xs">Rows per page <select className="ml-1 rounded border border-slate-300 px-2 py-1" value={pageSize} onChange={e=>{setPageSize(Number(e.target.value));setPage(1)}}><option value={50}>50</option><option value={100}>100</option></select></label><Pagination page={page} pages={pages} total={total} pageSize={pageSize} noun="receiving reports" onChange={setPage}/></div></>}</Card></div>{canCreate&&<ReceiveGoodsDialog open={creating} purchaseOrder={null} onClose={()=>setCreating(false)}/>} {canCreate&&<DirectReceiveDialog open={direct} onClose={()=>setDirect(false)}/>}</>;
}
