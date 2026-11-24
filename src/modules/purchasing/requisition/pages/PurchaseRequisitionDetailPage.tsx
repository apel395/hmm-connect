import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import useAuthorization from "@/hooks/useAuthorization";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { toast } from "sonner";
import DocumentActivity from "../../components/DocumentActivity";
import RejectDialog from "../../components/RejectDialog";
import {
  PurchasingDocumentHeader,
  PurchasingMetaGrid,
  PurchasingMetaItem,
  PurchasingNote,
  PurchasingSection,
  PurchasingStatusBadge,
  PurchasingTotals,
} from "../../components/PurchasingDocumentUI";
import ApprovalSummary from "../components/ApprovalSummary";
import PurchaseRequisitionForm from "../components/PurchaseRequisitionForm";
import { useApproval } from "../hooks/useApprovals";
import {
  useApprovePurchaseRequisition,
  usePurchaseRequisition,
  useRejectPurchaseRequisition,
  useReopenPurchaseRequisition,
  useSubmitPurchaseRequisition,
  useUpdatePurchaseRequisition,
} from "../hooks/usePurchaseRequisitions";

const money = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

const taxBadge = (item: any) => {
  const category = String(item.tax_category ?? "").toUpperCase();
  if (category === "REVIEW_REQUIRED") {
    return <Badge variant="warning">Tax Review</Badge>;
  }
  if (item.is_taxable) {
    return <Badge variant="info">PPN {Number(item.tax_rate ?? 0)}%</Badge>;
  }
  return <Badge variant="secondary">Non-PPN</Badge>;
};

function errorMessage(error: unknown) {
  const candidate = error as {
    response?: { data?: { detail?: string | { message?: string } } };
    message?: string;
  };
  const detail = candidate.response?.data?.detail;
  if (typeof detail === "string") return detail;
  return detail?.message ?? candidate.message ?? "Purchase requisition could not be loaded.";
}

export default function PurchaseRequisitionDetailPage() {
  const prId = Number(useParams().id);
  const prQuery = usePurchaseRequisition(prId);
  const approvalQuery = useApproval("PURCHASE_REQUISITION", prId);
  const data: any = prQuery.data;
  const approval = approvalQuery.data;

  const submit = useSubmitPurchaseRequisition();
  const approve = useApprovePurchaseRequisition();
  const reject = useRejectPurchaseRequisition();
  const reopen = useReopenPurchaseRequisition();
  const update = useUpdatePurchaseRequisition();
  const { isSuperuser, hasPermission } = useAuthorization();
  const [editing, setEditing] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);

  if (prQuery.isLoading) return <div className="py-24"><Loading /></div>;
  if (prQuery.isError || !data) {
    return (
      <Card className="mx-auto mt-12 max-w-2xl">
        <h2 className="text-lg font-semibold text-red-700">Purchase requisition could not be displayed</h2>
        <p className="mt-2 text-sm text-slate-600">{errorMessage(prQuery.error)}</p>
        <div className="mt-5 flex gap-3">
          <WorkspaceBackButton />
          <Button onClick={() => prQuery.refetch()}>Try Again</Button>
        </div>
      </Card>
    );
  }

  const admin = isSuperuser();
  const pendingApproval = data.status === "PENDING_APPROVAL";
  const approvalPending = approval?.status === "PENDING";
  const canSubmit = hasPermission("pr.submit") && data.status === "DRAFT" && Boolean(data.allowed_actions?.can_submit);
  const canApprove = hasPermission("pr.approve") && pendingApproval && approvalPending && Boolean(approval?.can_decide);
  const canReject = hasPermission("pr.approve") && pendingApproval && approvalPending && Boolean(approval?.can_decide);
  const canEdit = hasPermission("pr.edit") && Boolean(data.allowed_actions?.can_edit);
  const canReopen = admin && data.status !== "DRAFT" && Boolean(data.allowed_actions?.can_reopen ?? true);
  const canPrint = data.allowed_actions?.can_print !== false;

  const subtotal = Number(
    data.subtotal ??
      (data.items ?? []).reduce(
        (sum: number, item: any) => sum + Number(item.line_subtotal ?? item.quantity * item.estimated_price),
        0,
      ),
  );
  const taxAmount = Number(
    data.tax_amount ??
      (data.items ?? []).reduce((sum: number, item: any) => sum + Number(item.tax_amount ?? 0), 0),
  );
  const total = Number(data.total_amount ?? subtotal + taxAmount);

  const pendingStep = approval?.steps?.find((step: any) => step.status === "PENDING");
  const currentApprover =
    approval?.current_approver_role ??
    pendingStep?.approver_role_name ??
    "—";

  const act = async (operation: "submit" | "approve") => {
    try {
      if (operation === "submit") await submit.mutateAsync(data.id);
      if (operation === "approve") await approve.mutateAsync({ id: data.id, comment: "Approved" });
      toast.success(operation === "submit" ? "Purchase Requisition submitted." : "Approval completed.");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message ?? `${operation} failed.`);
    }
  };

  const submitRejection = async (comment: string) => {
    await reject.mutateAsync({ id: data.id, comment });
    setRejectOpen(false);
    toast.success("Document rejected.");
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

  const actions = (
    <>
      <WorkspaceBackButton />
      {canPrint && (
        <PrintPreviewButton
          src={`/purchase-requisitions/${data.id}/print`}
          title={`Purchase Requisition ${data.pr_number}`}
          ariaLabel="Preview purchase requisition"
        />
      )}
      {canEdit && <Button variant="outline" onClick={() => setEditing(true)}>Edit</Button>}
      {canReopen && (
        <Button variant="outline" loading={reopen.isPending} onClick={reopenForCorrection}>
          Reopen
        </Button>
      )}
      {canReject && (
        <Button variant="danger" loading={reject.isPending} onClick={() => setRejectOpen(true)}>
          Reject
        </Button>
      )}
      {canSubmit && <Button loading={submit.isPending} onClick={() => act("submit")}>Submit</Button>}
      {canApprove && (
        <Button variant="success" loading={approve.isPending} onClick={() => act("approve")}>
          Approve
        </Button>
      )}
    </>
  );

  return (
    <div className="space-y-5 pb-6">
      <PurchasingDocumentHeader
        eyebrow="Purchase Requisition"
        number={data.pr_number}
        status={data.status}
        actions={actions}
        meta={
          <>
            <span>Requester: <strong className="font-semibold text-slate-700">{data.requester_name ?? "—"}</strong></span>
            <span>Request date: <strong className="font-semibold text-slate-700">{data.request_date ?? "—"}</strong></span>
            <span>{data.items?.length ?? 0} items</span>
          </>
        }
      >
        <PurchasingMetaGrid>
          <PurchasingMetaItem label="Business Unit">{data.business_unit_name ?? "—"}</PurchasingMetaItem>
          <PurchasingMetaItem label="Department">{data.department_name ?? "—"}</PurchasingMetaItem>
          <PurchasingMetaItem label="Location">{data.location_name ?? "—"}</PurchasingMetaItem>
          <PurchasingMetaItem label="Valid Until">{data.expiry_date ?? "—"}</PurchasingMetaItem>
          <PurchasingMetaItem label="Workflow"><PurchasingStatusBadge value={approval?.status} /></PurchasingMetaItem>
          <PurchasingMetaItem label="Current Approver">{currentApprover}</PurchasingMetaItem>
        </PurchasingMetaGrid>
      </PurchasingDocumentHeader>

      <RejectDialog
        open={rejectOpen}
        pending={reject.isPending}
        title="Reject Purchase Requisition"
        onClose={() => setRejectOpen(false)}
        onReject={submitRejection}
      />

      {approvalQuery.isError && (
        <div role="alert" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          Approval details could not be loaded. The requisition is still available.
        </div>
      )}

      <div className="grid gap-5 lg:grid-cols-12">
        <div className="space-y-5 lg:col-span-8">
          <PurchasingSection title="Requisition Items" flush>
            <div className="overflow-x-auto">
              <table className="purchasing-document-table min-w-[1040px]">
                <thead>
                  <tr>
                    <th className="text-left">Product</th>
                    <th>UOM</th>
                    <th className="pd-amount">Qty</th>
                    <th className="pd-amount">Estimated Price</th>
                    <th className="pd-amount">Subtotal</th>
                    <th>Tax</th>
                    <th className="pd-amount">PPN</th>
                    <th className="pd-amount">Line Total</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.items ?? []).map((item: any, index: number) => {
                    const lineSubtotal = Number(item.line_subtotal ?? item.quantity * item.estimated_price);
                    const lineTax = Number(item.tax_amount ?? 0);
                    return (
                      <tr key={item.id ?? index}>
                        <td className="pd-primary-cell">
                          <div className="pd-strong">{item.product_name}</div>
                          <div className="pd-subtext">{item.product_code}</div>
                        </td>
                        <td>{item.uom ?? item.product_uom ?? "—"}</td>
                        <td className="pd-amount">{item.quantity}</td>
                        <td className="pd-amount">{money(item.estimated_price)}</td>
                        <td className="pd-amount">{money(lineSubtotal)}</td>
                        <td>{taxBadge(item)}</td>
                        <td className="pd-amount">{money(lineTax)}</td>
                        <td className="pd-amount pd-strong">{money(lineSubtotal + lineTax)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            <PurchasingTotals
              rows={[
                { label: "Subtotal", value: money(subtotal) },
                { label: "PPN", value: money(taxAmount) },
                { label: "Grand Total", value: money(total), emphasis: true },
              ]}
            />
          </PurchasingSection>

          <PurchasingNote>{data.notes}</PurchasingNote>
        </div>

        <div className="space-y-5 lg:col-span-4">
          <ApprovalSummary approval={approval} />
          <PurchasingSection title="Document Information">
            <div className="space-y-3 text-sm">
              <div className="flex justify-between gap-4">
                <span className="text-slate-500">PR Number</span>
                <span className="font-medium">{data.pr_number}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-slate-500">Total Items</span>
                <span className="font-medium">{data.items?.length ?? 0}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-slate-500">Grand Total</span>
                <span className="font-semibold tabular-nums">{money(total)}</span>
              </div>
              {!!data.generated_purchase_orders?.length && (
                <div className="border-t border-slate-200 pt-3">
                  <div className="mb-2 text-xs font-medium uppercase tracking-wide text-slate-400">
                    Generated Purchase Orders
                  </div>
                  {data.generated_purchase_orders.map((order: any) => (
                    <Link key={order.id} className="block font-medium text-emerald-700 hover:underline" to={`/purchase-orders/${order.id}`}>
                      {order.document_number}
                    </Link>
                  ))}
                </div>
              )}
            </div>
          </PurchasingSection>
        </div>
      </div>

      {editing && (
        <PurchaseRequisitionForm
          initialData={data}
          onClose={() => setEditing(false)}
          onSubmit={async (payload) => {
            try {
              await update.mutateAsync({ id: data.id, data: payload });
              setEditing(false);
              toast.success("Purchase requisition updated.");
            } catch (error: any) {
              toast.error(error?.response?.data?.detail || "Purchase requisition could not be updated.");
              throw error;
            }
          }}
        />
      )}

      {data.allowed_actions?.can_manage_attachments !== false && (
        <DocumentAttachments entityType="PURCHASE_REQUISITION" entityId={data.id} />
      )}
      {data.allowed_actions?.can_view_history !== false && (
        <DocumentActivity events={data.activity_history} />
      )}
    </div>
  );
}
