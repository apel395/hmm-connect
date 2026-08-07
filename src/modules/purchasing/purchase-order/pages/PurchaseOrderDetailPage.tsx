import { useState } from "react";
import { ArrowLeft } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";
import ReceiveGoodsDialog from "@/modules/purchasing/goods-receipts/components/ReceiveGoodsDialog";
import GoodsReceiptHistory from "../components/GoodsReceiptHistory";
import DocumentActivity from "../../components/DocumentActivity";
import PurchaseOrderForm from "../components/PurchaseOrderForm";
import { useApprovePurchaseOrder, usePurchaseOrder, useRejectPurchaseOrder, useSubmitPurchaseOrder, useUpdatePurchaseOrder } from "../hooks/usePurchaseOrders";
import type { ApprovalHistoryItem, PurchaseOrderItem } from "../types";
import useAuthorization from "@/hooks/useAuthorization";

const money = (value: unknown) => Number(value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function PurchaseOrderDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { data, isLoading } = usePurchaseOrder(Number(id));
  const submit = useSubmitPurchaseOrder();
  const approve = useApprovePurchaseOrder();
  const reject = useRejectPurchaseOrder();
  const update = useUpdatePurchaseOrder();
  const { isSuperuser } = useAuthorization();
  const [receiving, setReceiving] = useState(false);
  const [editing, setEditing] = useState(false);

  if (isLoading) return <Loading/>;
  if (!data) return null;

  const actions = data.allowed_actions ?? {};
  const admin = isSuperuser();
  const canEdit = admin || Boolean(actions.can_edit);
  const canApprove = admin || Boolean(actions.can_approve);
  const canReject = admin || Boolean(actions.can_reject);

  async function run(action: "submit" | "approve" | "reject") {
    try {
      if (action === "submit") await submit.mutateAsync(data.id);
      if (action === "approve") await approve.mutateAsync({ id: data.id, comment: "Approved" });
      if (action === "reject") {
        const comment = window.prompt("Reject reason");
        if (!comment) return;
        await reject.mutateAsync({ id: data.id, comment });
      }
      toast.success(action === "submit" ? "Purchase order submitted." : action === "approve" ? "Purchase order approved." : "Purchase order rejected.");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message ?? `${action} failed.`);
    }
  }

  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-4"><Button variant="outline" size="sm" onClick={() => navigate("/purchase-orders")}><ArrowLeft size={17}/> Back</Button><div><div className="text-sm text-slate-500">Purchase Order</div><div className="flex items-center gap-3"><h1 className="text-2xl font-bold">{data.po_number}</h1><Badge>{data.creation_type === "FROM_PR" ? "From PR" : "Direct"}</Badge><Badge>{data.status}</Badge></div></div></div>
      <div className="flex flex-wrap items-center gap-2">
        {actions.can_print !== false && <PrintPreviewButton src={`/purchase-orders/${data.id}/print`} title={`Purchase Order ${data.po_number}`} ariaLabel="Preview purchase order" />}
        {canEdit && <Button variant="outline" onClick={() => setEditing(true)}>Edit</Button>}
        {actions.can_submit && <Button loading={submit.isPending} onClick={() => run("submit")}>Submit</Button>}
        {canReject && data.status === "PENDING_APPROVAL" && <Button variant="danger" loading={reject.isPending} onClick={() => run("reject")}>Reject</Button>}
        {canApprove && data.status === "PENDING_APPROVAL" && <Button variant="success" loading={approve.isPending} onClick={() => run("approve")}>Approve</Button>}
        {actions.can_receive && <Button onClick={() => setReceiving(true)}>Receive</Button>}
      </div>
    </div>

    <Card><div className="grid gap-5 md:grid-cols-3 lg:grid-cols-6"><div><div className="text-xs text-slate-500">Supplier</div><div className="font-semibold">{data.supplier_name}</div></div><div><div className="text-xs text-slate-500">Department</div><div>{data.department_name ?? "—"}</div></div><div><div className="text-xs text-slate-500">Location</div><div>{data.location_name ?? "—"}</div></div><div><div className="text-xs text-slate-500">Order Date</div><div>{data.order_date}</div></div><div><div className="text-xs text-slate-500">Estimated Delivery</div><div>{data.expected_date ?? "—"}</div></div><div><div className="text-xs text-slate-500">Creation Type</div><div>{data.creation_type === "FROM_PR" ? "From PR" : "Direct Order"}</div></div></div>{data.source_pr_id && <div className="mt-5 border-t pt-4"><span className="mr-3 text-sm text-slate-500">Source PR:</span><Link className="font-medium text-emerald-700 hover:underline" to={`/purchase-requisitions/${data.source_pr_id}`}>{data.source_pr_number ?? `PR #${data.source_pr_id}`}</Link></div>}</Card>

    <Card className="overflow-hidden p-0"><div className="border-b bg-slate-50 px-5 py-4 font-semibold">Order Items</div><div className="overflow-x-auto"><table className="table-grid min-w-full text-sm"><thead><tr className="border-b"><th className="p-3 text-left">Item</th><th>UOM</th><th className="text-right">Ordered</th><th className="text-right">Received</th><th className="text-right">Unit Price</th><th className="p-3 text-right">Total</th></tr></thead><tbody>{data.items.map((item: PurchaseOrderItem) => <tr key={item.id} className="border-b"><td className="p-3"><div>{item.product_name}</div><div className="text-xs text-slate-500">{item.product_code}</div></td><td>{item.uom ?? "—"}</td><td className="text-right">{item.quantity}</td><td className="text-right">{item.received_quantity}</td><td className="text-right">{money(item.unit_price)}</td><td className="p-3 text-right">{money(item.total_price)}</td></tr>)}</tbody><tfoot><tr><td colSpan={5} className="p-3 text-right font-semibold">Total</td><td className="p-3 text-right text-lg font-bold">{money(data.total_amount)}</td></tr></tfoot></table></div></Card>

    <Card><h2 className="mb-4 font-semibold">Approval Progress</h2><div className="grid gap-3 md:grid-cols-2">{data.approval_history?.map((step: ApprovalHistoryItem) => <div key={step.level} className="rounded border p-3"><div className="flex justify-between"><span className="font-medium">{step.level}. {step.name}</span><Badge>{step.status}</Badge></div><div className="mt-2 text-sm text-slate-600">{step.approver_name ?? step.approver_role}</div>{step.decided_at && <div className="text-xs text-slate-500">{new Date(step.decided_at).toLocaleString()}</div>}{step.comment && <p className="mt-2 text-sm">{step.comment}</p>}</div>)}</div></Card>

    {editing && <PurchaseOrderForm open initialData={data} loading={update.isPending} onClose={() => setEditing(false)} onSubmit={async (payload) => { await update.mutateAsync({ id: data.id, payload }); setEditing(false); toast.success("Purchase order updated."); }}/>} 
    <GoodsReceiptHistory purchaseOrderId={data.id}/>
    {actions.can_manage_attachments !== false && <DocumentAttachments entityType="PURCHASE_ORDER" entityId={data.id}/>} 
    {actions.can_view_history !== false && <DocumentActivity events={data.activity_history}/>} 
    <ReceiveGoodsDialog open={receiving} purchaseOrder={data} onClose={() => setReceiving(false)}/>
  </div>;
}
