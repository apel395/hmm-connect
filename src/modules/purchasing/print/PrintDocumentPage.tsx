import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import api from "@/api/client";
import Loading from "@/components/ui/Loading";
import DocumentPrintTemplate, { type PrintSignature } from "@/components/print/DocumentPrintTemplate";

interface PrintItem { id:number;product_code?:string;product_name:string;uom?:string;quantity:number;unit_price?:number;estimated_price?:number;unit_cost?:number;total_price?:number;line_total?:number }
interface ApprovalRecord {level:number;name:string;status:string;approver_name?:string|null;decided_at?:string|null;comment?:string|null;signature_name?:string|null;signature_label?:string|null;signature_image?:string|null}
interface PrintDocument {
  document_type:string;brand_name?:string;hotel_name?:string;pr_number?:string;ml_number?:string;po_number?:string;receipt_number?:string;
  request_date?:string;order_date?:string;received_at?:string;expected_date?:string;expiry_date?:string;
  supplier_name?:string;requester_name?:string;status?:string;destination_type?:string;warehouse_name?:string|null;
  delivery_note_number?:string|null;external_reference?:string|null;business_unit_name?:string|null;department_name?:string|null;location_name?:string|null;
  business_unit_id?:number|null;department_id?:number|null;location_id?:number|null;notes?:string|null;total_amount?:number;total_value?:number;
  printed_by:string;generated_at:string;items:PrintItem[];approval_history?:ApprovalRecord[];source_pr_number?:string|null;purchase_order_number?:string|null;
}
const money=(value:unknown)=>Number(value??0).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});
const displayDate=(value?:string)=>value?new Date(value).toLocaleDateString():"—";
const indonesianLongDate=(value?:string)=>value?new Date(`${value.slice(0,10)}T00:00:00`).toLocaleDateString("id-ID",{day:"numeric",month:"long",year:"numeric"}):"—";
const addCalendarDays=(value:string,days:number)=>{const date=new Date(`${value.slice(0,10)}T00:00:00`);date.setDate(date.getDate()+days);return date.toISOString().slice(0,10)};

function approvalSignatures(data:PrintDocument):PrintSignature[]{
  const history=data.approval_history??[];
  const approved=history.filter(record=>record.status==="APPROVED");
  const authenticated=approved.filter(record=>Boolean(record.signature_image));
  if(authenticated.length){
    return authenticated.map(record=>({label:record.signature_label||record.name||`Approval Level ${record.level}`,name:record.signature_name||record.approver_name||record.status,imageSrc:record.signature_image||undefined}));
  }
  return approved.slice(0,3).map(record=>({label:record.name||`Approval Level ${record.level}`,name:record.approver_name??record.status}));
}

export default function PrintDocumentPage({kind}:{kind:"purchase-requisitions"|"market-lists"|"purchase-orders"|"goods-receipts"}){
  const{id}=useParams();
  const query=useQuery({queryKey:[kind,id,"print"],queryFn:async()=>(await api.get<PrintDocument>(`/${kind}/${id}/print`)).data,enabled:Boolean(id)});
  if(query.isLoading)return <Loading/>;
  if(!query.data)return <p>Document could not be loaded.</p>;
  const data=query.data;
  const isReceipt=kind==="goods-receipts";
  const isPr=kind==="purchase-requisitions";
  const isMl=kind==="market-lists";
  const isPo=kind==="purchase-orders";
  const number=data.pr_number??data.ml_number??data.po_number??data.receipt_number;
  const date=data.request_date??data.order_date??data.received_at;
  const total=isReceipt?(data.total_value??data.items.reduce((sum,item)=>sum+Number(item.line_total??Number(item.quantity)*Number(item.unit_cost??0)),0)):(data.total_amount??data.items.reduce((sum,item)=>sum+Number(item.total_price??Number(item.quantity)*Number(item.unit_price??item.estimated_price??0)),0));
  const deliveryDeadline=isPo?(data.expected_date??(data.order_date?addCalendarDays(data.order_date,3):undefined)):undefined;
  const fields=[
    ...((isPr||isMl)?[{label:"REQUESTER",value:data.requester_name}]:[{label:"SUPPLIER",value:data.supplier_name}]),
    ...(!isPr&&!isMl&&data.source_pr_number?[{label:"PR #",value:data.source_pr_number}]:[]),
    ...(isReceipt?[{label:"PO #",value:data.purchase_order_number??data.po_number},{label:"DELIVERY NOTE",value:data.delivery_note_number??data.external_reference},{label:"DESTINATION",value:data.destination_type==="WAREHOUSE"?`Warehouse — ${data.warehouse_name??""}`:"Direct Use"}]:[]),
    {label:"UNIT BISNIS",value:data.business_unit_name??(data.business_unit_id?`#${data.business_unit_id}`:undefined)},
    {label:"LOCATION",value:data.location_name??(data.location_id?`#${data.location_id}`:undefined)},
    {label:"DEPARTMENT",value:data.department_name??(data.department_id?`#${data.department_id}`:undefined)},
    ...(data.expected_date?[{label:"DELIVERY DATE",value:displayDate(data.expected_date)}]:[]),
    ...(data.expiry_date?[{label:"VALID UNTIL",value:displayDate(data.expiry_date)}]:[]),
  ];
  const columns=[
    {label:"DESCRIPTION",align:"left" as const,render:(item:PrintItem)=><><div>{item.product_name}</div>{item.product_code&&<div className="text-[10px] text-slate-500">{item.product_code}</div>}</>},
    {label:"Qty",align:"right" as const,render:(item:PrintItem)=>item.quantity},
    {label:"Uom",align:"center" as const,render:(item:PrintItem)=>item.uom??"—"},
    {label:"Price",align:"right" as const,render:(item:PrintItem)=>money(isReceipt?item.unit_cost:item.unit_price??item.estimated_price??0)},
    {label:"AMOUNT",align:"right" as const,render:(item:PrintItem)=>money(isReceipt?(item.line_total??Number(item.quantity)*Number(item.unit_cost??0)):(item.total_price??Number(item.quantity)*Number(item.unit_price??item.estimated_price??0)))},
  ];
  const signatures=approvalSignatures(data);
  const poTerms=isPo?<section className="avoid-break mt-7 text-[11px] leading-5"><div className="mb-1 font-bold">Syarat & Ketentuan</div><ol className="list-decimal space-y-0.5 pl-5"><li>Barang harus dikirim paling lambat {indonesianLongDate(deliveryDeadline)} ke lokasi yang tertera pada PO ini.</li><li>Pembayaran dilakukan melalui transfer bank setelah 60 hari sejak barang diterima dan diverifikasi.</li><li>Faktur asli dan dokumen pendukung harus dilampirkan bersama pengiriman barang.</li><li>Apabila terjadi keterlambatan pengiriman ataupun selisih, pihak pemasok wajib memberikan pemberitahuan tertulis.</li></ol></section>:undefined;
  return <DocumentPrintTemplate title={isReceipt?"Receiving Report":data.document_type} documentNumber={number} documentDate={displayDate(date)} status={data.status} fields={fields} columns={columns} rows={data.items} rowKey={(item)=>item.id} totals={[{label:"TOTAL",value:money(total),emphasis:true}]} notes={data.notes} extraAfterTable={poTerms} signatures={signatures.length?signatures:[{label:"Prepared By",name:data.printed_by},{label:"Checked By"},{label:"Approved By"}]} footer={<>Printed by {data.printed_by} · {new Date(data.generated_at).toLocaleString()}</>}/>
}