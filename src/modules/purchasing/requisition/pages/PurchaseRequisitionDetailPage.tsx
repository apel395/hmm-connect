import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";
import DocumentActivity from "../../components/DocumentActivity";
import WorkflowHeader from "../components/WorkflowHeader";
import WorkflowActionBar from "../components/WorkflowActionBar";
import ApprovalSummary from "../components/ApprovalSummary";
import PurchaseRequisitionForm from "../components/PurchaseRequisitionForm";
import {
  usePurchaseRequisition,
  useSubmitPurchaseRequisition,
  useApprovePurchaseRequisition,
  useRejectPurchaseRequisition,
  useReopenPurchaseRequisition,
  useUpdatePurchaseRequisition,
} from "../hooks/usePurchaseRequisitions";
import { useApproval } from "../hooks/useApprovals";
import useAuthorization from "@/hooks/useAuthorization";

const money = (value: unknown) => Number(value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const badgeVariant = (status?: string) => {
  switch ((status ?? "").toUpperCase()) {
    case "APPROVED": return "success";
    case "PENDING": case "SUBMITTED": case "PENDING_APPROVAL": return "warning";
    case "REJECTED": return "danger";
    case "CANCELLED": return "secondary";
    default: return "outline";
  }
};

function errorMessage(error: unknown) {
  const candidate = error as { response?: { data?: { detail?: string | { message?: string } } }; message?: string };
  const detail = candidate.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return detail?.message ?? candidate.message ?? "Purchase requisition could not be loaded.";
}

export default function PurchaseRequisitionDetailPage() {
  const navigate = useNavigate();
  const prId = Number(useParams().id);
  const prQuery = usePurchaseRequisition(prId);
  const approvalQuery = useApproval("PURCHASE_REQUISITION", prId);
  const data = prQuery.data;
  const approval = approvalQuery.data;
  const submit = useSubmitPurchaseRequisition();
  const approve = useApprovePurchaseRequisition();
  const reject = useRejectPurchaseRequisition();
  const reopen = useReopenPurchaseRequisition();
  const update = useUpdatePurchaseRequisition();
  const { isSuperuser } = useAuthorization();
  const [editing, setEditing] = useState(false);

  if (prQuery.isLoading) return <div className="py-24"><Loading/></div>;
  if (prQuery.isError || !data) {
    return <Card className="mx-auto mt-12 max-w-2xl"><h2 className="text-lg font-semibold text-red-700">Purchase requisition could not be displayed</h2><p className="mt-2 text-sm text-slate-600">{errorMessage(prQuery.error)}</p><div className="mt-5 flex gap-3"><Button variant="outline" onClick={() => navigate("/purchase-requisitions")}>Back</Button><Button onClick={() => prQuery.refetch()}>Try Again</Button></div></Card>;
  }

  const admin = isSuperuser();
  const pendingApproval = data.status === "PENDING_APPROVAL";
  const canSubmit = data.status === "DRAFT" && Boolean(data.allowed_actions?.can_submit);
  const canApprove = pendingApproval && (admin || Boolean(data.allowed_actions?.can_approve));
  const canReject = pendingApproval && (admin || Boolean(data.allowed_actions?.can_reject));
  const canEdit = data.status === "DRAFT" && Boolean(data.allowed_actions?.can_edit);
  const canReopen = admin && data.status !== "DRAFT" && Boolean(data.allowed_actions?.can_reopen ?? true);
  const total = (data.items ?? []).reduce((sum: number, item: any) => sum + Number(item.total_price ?? item.quantity * item.estimated_price), 0);

  const act = async (operation: "submit" | "approve" | "reject") => {
    try {
      if (operation === "submit") await submit.mutateAsync(data.id);
      if (operation === "approve") await approve.mutateAsync({ id: data.id, comment: "Approved" });
      if (operation === "reject") {
        const comment = window.prompt("Reject reason");
        if (!comment) return;
        await reject.mutateAsync({ id: data.id, comment });
      }
      toast.success(operation === "submit" ? "Purchase Requisition submitted." : operation === "approve" ? "Approval completed." : "Document rejected.");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message ?? `${operation} failed.`);
    }
  };

  const reopenForCorrection = async () => {
    if (!window.confirm("Reopen this purchase requisition for correction? It will return to Draft and require approval again.")) return;
    try {
      await reopen.mutateAsync(data.id);
      toast.success("Purchase requisition reopened for correction.");
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Purchase requisition could not be reopened.");
    }
  };

  return <div className="space-y-6">
    <PageHeader title={data.pr_number} description="Purchase Requisition" actions={<Badge variant={badgeVariant(data.status)}>{data.status}</Badge>}/>
    <WorkflowHeader document={data} approval={approval}/>
    {canReopen && <div className="flex justify-end"><Button variant="outline" loading={reopen.isPending} onClick={reopenForCorrection}>Reopen for Correction</Button></div>}
    <WorkflowActionBar document={data} approval={approval} canSubmit={canSubmit} canApprove={canApprove} canReject={canReject} canEdit={canEdit} canPrint={data.allowed_actions?.can_print !== false} submitting={submit.isPending} approving={approve.isPending} rejecting={reject.isPending} onBack={() => navigate("/purchase-requisitions")} onSubmit={() => act("submit")} onEdit={() => setEditing(true)} onApprove={() => act("approve")} onReject={() => act("reject")}/>

    {approvalQuery.isError && <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">Approval details are not available yet. The purchase requisition itself is still accessible.</div>}

    <div className="grid gap-6 lg:grid-cols-12">
      <div className="space-y-6 lg:col-span-8">
        <Card className="overflow-hidden p-0"><div className="border-b bg-slate-50 px-6 py-4 font-semibold">Requisition Items</div><div className="overflow-x-auto"><table className="table-grid min-w-[800px] w-full table-fixed text-sm"><thead className="bg-slate-100"><tr><th className="w-[36%] px-5 py-3 text-left">Product</th><th className="w-24">UOM</th><th className="w-28 text-right">Qty</th><th className="w-44 text-right">Estimated Price</th><th className="w-48 px-5 text-right">Total</th></tr></thead><tbody>{(data.items ?? []).map((item: any, index: number) => <tr key={item.id ?? index} className="border-t"><td className="px-5 py-4"><div className="font-medium">{item.product_name}</div><div className="text-xs text-slate-500">{item.product_code}</div></td><td>{item.uom ?? item.product_uom ?? "—"}</td><td className="text-right tabular-nums">{item.quantity}</td><td className="text-right tabular-nums">{money(item.estimated_price)}</td><td className="px-5 text-right font-semibold tabular-nums">{money(item.total_price ?? item.quantity * item.estimated_price)}</td></tr>)}</tbody><tfoot className="border-t-2 bg-slate-50"><tr><td colSpan={4} className="px-5 py-4 text-right font-semibold">Grand Total</td><td className="px-5 text-right text-lg font-bold tabular-nums">{money(total)}</td></tr></tfoot></table></div></Card>
        <Card><h3 className="mb-3 font-semibold">Notes</h3><div className="rounded bg-slate-50 p-4">{data.notes || "No notes provided."}</div></Card>
      </div>
      <div className="space-y-6 lg:col-span-4"><ApprovalSummary approval={approval}/><Card><h3 className="mb-4 font-semibold">Information</h3><div className="space-y-3 text-sm"><div className="flex justify-between"><span className="text-slate-500">PR Number</span><span className="font-medium">{data.pr_number}</span></div><div className="flex justify-between"><span className="text-slate-500">Business Unit</span><span>{data.business_unit_name ?? "—"}</span></div><div className="flex justify-between"><span className="text-slate-500">Department</span><span>{data.department_name ?? "—"}</span></div><div className="flex justify-between"><span className="text-slate-500">Location</span><span>{data.location_name ?? "—"}</span></div><div className="flex justify-between"><span className="text-slate-500">Request Date</span><span>{data.request_date ?? "—"}</span></div><div className="flex justify-between"><span className="text-slate-500">Valid Until</span><span>{data.expiry_date ?? "—"}</span></div><div className="flex justify-between"><span className="text-slate-500">Status</span><Badge variant={badgeVariant(data.status)}>{data.status}</Badge></div><div className="flex justify-between"><span className="text-slate-500">Total Items</span><span>{data.items?.length ?? 0}</span></div>{!!data.generated_purchase_orders?.length && <div className="border-t pt-3"><div className="mb-2 text-slate-500">Generated Purchase Orders</div>{data.generated_purchase_orders.map((order: any) => <Link key={order.id} className="mr-3 font-medium text-emerald-700" to={`/purchase-orders/${order.id}`}>{order.document_number}</Link>)}</div>}</div></Card></div>
    </div>

    {editing && <PurchaseRequisitionForm initialData={data} onClose={() => setEditing(false)} onSubmit={async (payload) => { try { await update.mutateAsync({ id: data.id, data: payload }); setEditing(false); toast.success("Purchase requisition updated."); } catch (error: any) { toast.error(error?.response?.data?.detail || "Purchase requisition could not be updated."); throw error; } }}/>} 
    {data.allowed_actions?.can_manage_attachments !== false && <DocumentAttachments entityType="PURCHASE_REQUISITION" entityId={data.id}/>} 
    {data.allowed_actions?.can_view_history !== false && <DocumentActivity events={data.activity_history}/>} 
  </div>;
}
