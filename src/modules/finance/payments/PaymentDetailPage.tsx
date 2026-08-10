import { ArrowLeft } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";
import DocumentActivity from "@/modules/purchasing/components/DocumentActivity";
import { getPayment, paymentAction } from "./api";

const money=(value:unknown)=>Number(value||0).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});

export default function PaymentDetailPage(){
 const{id}=useParams();const navigate=useNavigate();const qc=useQueryClient();
 const query=useQuery({queryKey:["payment",id],queryFn:()=>getPayment(Number(id)),enabled:!!id});
 const refreshFinance=()=>{
   qc.invalidateQueries({queryKey:["payment",id]});
   qc.invalidateQueries({queryKey:["payments"]});
   qc.invalidateQueries({queryKey:["eligible-payment-invoices"]});
   qc.invalidateQueries({queryKey:["supplier-invoices"]});
   qc.invalidateQueries({queryKey:["accounts-payable-aging"]});
   qc.invalidateQueries({queryKey:["finance-dashboard"]});
   qc.invalidateQueries({queryKey:["cash-flow"]});
   qc.invalidateQueries({queryKey:["cash-accounts"]});
   qc.invalidateQueries({queryKey:["journal-entries"]});
   qc.invalidateQueries({queryKey:["general-ledger"]});
   qc.invalidateQueries({queryKey:["trial-balance"]});
   qc.invalidateQueries({queryKey:["balance-sheet"]});
   qc.invalidateQueries({queryKey:["profit-loss"]});
 };
 const action=useMutation({mutationFn:async(name:string)=>{if(name==="approve"){await paymentAction(Number(id),"approve");try{await paymentAction(Number(id),"generate-journal")}catch(error:any){throw Object.assign(error,{paymentApproved:true})}return}return paymentAction(Number(id),name)},onSuccess:(_,name)=>{toast.success(name==="approve"?"Payment approved and draft journal generated from Posting Rules":`Payment ${name} complete`);refreshFinance()},onError:(error:any)=>{if(error?.paymentApproved)toast.error(error?.response?.data?.detail||"Payment was approved, but its journal could not be generated. Configure the SUPPLIER_PAYMENT Posting Rule.");else toast.error(error.response?.data?.detail||"Payment action failed");refreshFinance()}});
 if(query.isLoading)return <Loading/>;if(!query.data)return <p>Payment not found.</p>;
 const payment=query.data,allowed=payment.allowed_actions??{};
 return <div className="space-y-6">
  <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><Button variant="outline" onClick={()=>navigate("/payments")}><ArrowLeft size={16}/> Back</Button><h1 className="text-2xl font-bold">{payment.payment_number}</h1><Badge>{payment.status}</Badge></div><div className="flex gap-2"><PrintPreviewButton src={`/payments/${payment.id}/print`} title={`Payment Request ${payment.payment_number}`} ariaLabel="Preview payment request"/>{allowed.can_approve&&<Button loading={action.isPending} onClick={()=>action.mutate("approve")}>Approve & Create Journal</Button>}{allowed.can_generate_journal&&<Button loading={action.isPending} onClick={()=>action.mutate("generate-journal")}>Create Missing Journal</Button>}{allowed.can_post&&<Button loading={action.isPending} onClick={()=>action.mutate("post")}>Post Payment</Button>}{allowed.can_void&&<Button variant="danger" onClick={()=>action.mutate("void")}>Void</Button>}</div></div>
  <Card><div className="grid gap-4 md:grid-cols-4"><div><small>Supplier</small><div>{payment.supplier_name}</div></div><div><small>Payment Date</small><div>{payment.payment_date}</div></div><div><small>Method</small><div>{payment.payment_method}</div></div><div><small>Currency</small><div>{payment.currency}</div></div><div><small>Reference</small><div>{payment.reference_number||"—"}</div></div><div><small>Cheque Number</small><div>{payment.cheque_number||"—"}</div></div><div><small>Total</small><div>{money(payment.total_amount)}</div></div><div><small>Funded</small><div>{money(payment.funded_amount)}</div></div></div></Card>
  <Card className="overflow-x-auto"><h2 className="mb-3 font-semibold">Invoice Allocations</h2><table className="table-grid w-full text-sm"><thead><tr><th>Invoice</th><th>Supplier Ref</th><th>Date</th><th>Due Date</th><th className="text-right">Invoice Total</th><th className="text-right">Allocated</th></tr></thead><tbody>{payment.allocations.map((row:any)=><tr key={row.id} className="border-t"><td><Link className="font-medium text-emerald-700 hover:underline" to={`/supplier-invoices/${row.supplier_invoice_id}`}>{row.invoice_number}</Link></td><td>{row.supplier_invoice_number||"—"}</td><td>{row.invoice_date}</td><td>{row.due_date||"—"}</td><td className="text-right">{money(row.invoice_total)}</td><td className="text-right font-medium">{money(row.allocated_amount)}</td></tr>)}</tbody></table><div className="mt-4 text-right font-bold">Allocated: {money(payment.allocated_amount)}</div></Card>
  <Card className="overflow-x-auto"><h2 className="mb-3 font-semibold">Funding Accounts</h2><table className="table-grid w-full text-sm"><thead><tr><th>Bank</th><th>Account Name</th><th>Account Number</th><th className="text-right">Amount</th></tr></thead><tbody>{payment.funding_lines.map((row:any)=><tr key={row.id} className="border-t"><td>{row.bank_name}</td><td>{row.account_name}</td><td>{row.account_number}</td><td className="text-right">{money(row.amount)}</td></tr>)}</tbody></table><div className="mt-4 text-right font-bold">Funded: {money(payment.funded_amount)}</div></Card>
  <Card><h2 className="font-semibold">Accounting</h2>{payment.journal_entry_id?<p className="mt-2">Related Journal: <Link className="font-medium text-emerald-700 hover:underline" to={`/journal-entries/${payment.journal_entry_id}`}>{payment.journal_number}</Link></p>:<p className="mt-2 text-sm text-slate-500">A draft journal is created automatically after approval using the SUPPLIER_PAYMENT Posting Rule.</p>}<h2 className="mt-5 font-semibold">Notes</h2><p>{payment.notes||"—"}</p></Card>
  <DocumentAttachments entityType="PAYMENT" entityId={payment.id}/><DocumentActivity events={payment.activity_history}/>
 </div>
}
