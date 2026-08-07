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

const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function PaymentDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const query = useQuery({ queryKey: ["payment", id], queryFn: () => getPayment(Number(id)), enabled: !!id });
  const action = useMutation({ mutationFn: (name: string) => paymentAction(Number(id), name), onSuccess: (_, name) => { toast.success(name === "generate-journal" ? "Draft journal generated" : `Payment ${name} complete`); queryClient.invalidateQueries({ queryKey: ["payment", id] }); }, onError: (error: any) => toast.error(error.response?.data?.detail || "Payment action failed") });
  if (query.isLoading) return <Loading/>;
  if (!query.data) return <p>Payment not found.</p>;
  const payment = query.data;
  const allowed = payment.allowed_actions ?? {};
  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-3"><Button variant="outline" onClick={() => navigate("/payments")}><ArrowLeft size={16}/> Back</Button><h1 className="text-2xl font-bold">{payment.payment_number}</h1><Badge>{payment.status}</Badge></div><div className="flex gap-2"><PrintPreviewButton src={`/payments/${payment.id}/print`} title={`Payment Voucher ${payment.payment_number}`} ariaLabel="Preview payment voucher" />{allowed.can_approve && <Button onClick={() => action.mutate("approve")}>Approve</Button>}{allowed.can_generate_journal && <Button onClick={() => action.mutate("generate-journal")}>Generate Journal</Button>}{allowed.can_post && <Button onClick={() => action.mutate("post")}>Post</Button>}{allowed.can_void && <Button variant="danger" onClick={() => action.mutate("void")}>Void</Button>}</div></div>
    <Card><div className="grid gap-4 md:grid-cols-4"><div><small>Supplier</small><div>{payment.supplier_name}</div></div><div><small>Payment Date</small><div>{payment.payment_date}</div></div><div><small>Method</small><div>{payment.payment_method}</div></div><div><small>Currency</small><div>{payment.currency}</div></div><div><small>Reference</small><div>{payment.reference_number || "—"}</div></div><div><small>Cheque Number</small><div>{payment.cheque_number || "—"}</div></div><div><small>Total</small><div>{money(payment.total_amount)}</div></div><div><small>Funded</small><div>{money(payment.funded_amount)}</div></div></div></Card>
    <Card className="overflow-x-auto"><h2 className="mb-3 font-semibold">Invoice Allocations</h2><table className="table-grid w-full text-sm"><thead><tr><th>Invoice</th><th>Date</th><th>Due Date</th><th className="text-right">Invoice Total</th><th className="text-right">Allocated</th></tr></thead><tbody>{payment.allocations.map((row: any) => <tr key={row.id} className="border-t"><td><Link className="text-emerald-700" to={`/supplier-invoices/${row.supplier_invoice_id}`}>{row.invoice_number}</Link></td><td>{row.invoice_date}</td><td>{row.due_date || "—"}</td><td className="text-right">{money(row.invoice_total)}</td><td className="text-right">{money(row.allocated_amount)}</td></tr>)}</tbody></table><div className="mt-4 text-right font-bold">Allocated: {money(payment.allocated_amount)}</div></Card>
    <Card className="overflow-x-auto"><h2 className="mb-3 font-semibold">Funding Accounts</h2><table className="table-grid w-full text-sm"><thead><tr><th>Bank</th><th>Account Name</th><th>Account Number</th><th className="text-right">Amount</th></tr></thead><tbody>{payment.funding_lines.map((row: any) => <tr key={row.id} className="border-t"><td>{row.bank_name}</td><td>{row.account_name}</td><td>{row.account_number}</td><td className="text-right">{money(row.amount)}</td></tr>)}</tbody></table><div className="mt-4 text-right font-bold">Funded: {money(payment.funded_amount)}</div></Card>
    <Card><h2 className="font-semibold">Notes</h2><p>{payment.notes || "—"}</p>{payment.journal_entry_id && <p className="mt-3">Related Journal: <Link className="text-emerald-700" to={`/journal-entries/${payment.journal_entry_id}`}>{payment.journal_number}</Link></p>}</Card>
    <DocumentAttachments entityType="PAYMENT" entityId={payment.id}/><DocumentActivity events={payment.activity_history}/>
  </div>;
}
