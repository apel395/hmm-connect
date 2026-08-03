import { useEffect, useState } from "react";
import { ArrowLeft, Printer } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import Loading from "@/components/ui/Loading";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";
import ReceiveGoodsDialog from "@/modules/purchasing/goods-receipts/components/ReceiveGoodsDialog";
import GoodsReceiptHistory from "../components/GoodsReceiptHistory";
import DocumentActivity from "../../components/DocumentActivity";
import { useApprovePurchaseOrder, usePurchaseOrder, useRejectPurchaseOrder, useSubmitPurchaseOrder, useUpdatePurchaseOrder } from "../hooks/usePurchaseOrders";
import type { ApprovalHistoryItem, PurchaseOrderItem } from "../types";

export default function PurchaseOrderDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { data, isLoading } = usePurchaseOrder(Number(id));
  const submit = useSubmitPurchaseOrder(), approve = useApprovePurchaseOrder(), reject = useRejectPurchaseOrder(), update = useUpdatePurchaseOrder();
  const [receiving, setReceiving] = useState(false), [editing, setEditing] = useState(false);
  const [expectedDate, setExpectedDate] = useState(""), [notes, setNotes] = useState("");
  useEffect(() => { if (data) { setExpectedDate(data.expected_date ?? ""); setNotes(data.notes ?? ""); } }, [data]);
  if (isLoading) return <Loading/>;
  if (!data) return null;
  const actions = data.allowed_actions;
  const save = async () => {
    await update.mutateAsync({ id: data.id, payload: {
      supplier_id: data.supplier_id, expected_date: expectedDate, expiry_date: data.expiry_date,
      notes,
      purchase_requisition_ids: data.purchase_requisition_ids ?? [],
      items: data.items.map((item: PurchaseOrderItem) => ({ product_id: item.product_id, quantity: Number(item.quantity), unit_price: Number(item.unit_price), purchase_requisition_item_id: item.purchase_requisition_item_id })),
    }});
    setEditing(false); toast.success("Purchase order updated.");
  };
  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-4"><div className="flex items-center gap-4"><Button variant="outline" size="sm" onClick={() => navigate("/purchase-orders")}><ArrowLeft size={17}/> Back</Button><div><div className="text-sm text-slate-500">Purchase Order</div><div className="flex items-center gap-3"><h1 className="text-2xl font-bold">{data.po_number}</h1><Badge>{data.creation_type === "FROM_PR" ? "From PR" : "Direct"}</Badge><Badge>{data.status}</Badge></div></div></div>
      <div className="flex items-center gap-2">{actions?.can_print !== false && <Button variant="outline" aria-label="Print purchase order" title="Print" onClick={() => window.open(`/purchase-orders/${data.id}/print`, "_blank")}><Printer size={18}/></Button>}{actions?.can_edit && <Button variant="outline" onClick={() => setEditing(!editing)}>Edit</Button>}{actions?.can_submit && <Button loading={submit.isPending} onClick={() => submit.mutate(data.id)}>Submit</Button>}{actions?.can_reject && <Button variant="danger" loading={reject.isPending} onClick={() => { const comment = window.prompt("Reject reason"); if (comment) reject.mutate({ id: data.id, comment }); }}>Reject</Button>}{actions?.can_approve && <Button variant="success" loading={approve.isPending} onClick={() => approve.mutate({ id: data.id, comment: "Approved" })}>Approve</Button>}{actions?.can_receive && <Button onClick={() => setReceiving(true)}>Receive</Button>}</div></div>
    {editing && <Card><h2 className="mb-4 font-semibold">Edit Purchase Order</h2><div className="grid gap-4 md:grid-cols-2"><label className="text-sm font-medium">Estimated Delivery Date<Input type="date" value={expectedDate} onChange={(event) => setExpectedDate(event.target.value)}/></label><label className="text-sm font-medium">Notes<Input value={notes} onChange={(event) => setNotes(event.target.value)}/></label></div><div className="mt-4 flex justify-end gap-2"><Button variant="outline" onClick={() => setEditing(false)}>Cancel</Button><Button loading={update.isPending} onClick={save}>Save</Button></div></Card>}
    <Card><div className="grid gap-5 md:grid-cols-3 lg:grid-cols-6"><div><div className="text-xs text-slate-500">Supplier</div><div className="font-semibold">{data.supplier_name}</div></div><div><div className="text-xs text-slate-500">Department</div><div>{data.department_name ?? "—"}</div></div><div><div className="text-xs text-slate-500">Location</div><div>{data.location_name ?? "—"}</div></div><div><div className="text-xs text-slate-500">Order Date</div><div>{data.order_date}</div></div><div><div className="text-xs text-slate-500">Estimated Delivery</div><div>{data.expected_date ?? "—"}</div></div><div><div className="text-xs text-slate-500">Creation Type</div><div>{data.creation_type === "FROM_PR" ? "From PR" : "Direct Order"}</div></div></div>
      {data.source_pr_id && <div className="mt-5 border-t pt-4"><span className="mr-3 text-sm text-slate-500">Source PR:</span><Link className="font-medium text-emerald-700 hover:underline" to={`/purchase-requisitions/${data.source_pr_id}`}>{data.source_pr_number ?? `PR #${data.source_pr_id}`}</Link></div>}</Card>
    <Card className="overflow-hidden p-0"><div className="border-b bg-slate-50 px-5 py-4 font-semibold">Order Items</div><table className="w-full text-sm"><thead><tr className="border-b"><th className="p-3 text-left">Item</th><th className="text-right">Ordered</th><th className="text-right">Received</th><th className="text-right">Unit Price</th><th className="p-3 text-right">Total</th></tr></thead><tbody>{data.items.map((item: PurchaseOrderItem) => <tr key={item.id} className="border-b"><td className="p-3"><div>{item.product_name}</div><div className="text-xs text-slate-500">{item.product_code}</div></td><td className="text-right">{item.quantity}</td><td className="text-right">{item.received_quantity}</td><td className="text-right">{Number(item.unit_price).toLocaleString()}</td><td className="p-3 text-right">{Number(item.total_price).toLocaleString()}</td></tr>)}</tbody><tfoot><tr><td colSpan={4} className="p-3 text-right font-semibold">Total</td><td className="p-3 text-right text-lg font-bold">{Number(data.total_amount).toLocaleString()}</td></tr></tfoot></table></Card>
    <Card><h2 className="mb-4 font-semibold">Approval Progress</h2><div className="grid gap-3 md:grid-cols-2">{data.approval_history?.map((step: ApprovalHistoryItem) => <div key={step.level} className="rounded border p-3"><div className="flex justify-between"><span className="font-medium">{step.level}. {step.name}</span><Badge>{step.status}</Badge></div><div className="mt-2 text-sm text-slate-600">{step.approver_name ?? step.approver_role}</div>{step.decided_at && <div className="text-xs text-slate-500">{new Date(step.decided_at).toLocaleString()}</div>}{step.comment && <p className="mt-2 text-sm">{step.comment}</p>}</div>)}</div></Card>
    <GoodsReceiptHistory purchaseOrderId={data.id}/>
    {actions?.can_manage_attachments !== false && <DocumentAttachments entityType="PURCHASE_ORDER" entityId={data.id}/>}
    {actions?.can_view_history !== false && <DocumentActivity events={data.activity_history}/>}
    <ReceiveGoodsDialog open={receiving} purchaseOrder={data} onClose={() => setReceiving(false)}/>
  </div>;
}
