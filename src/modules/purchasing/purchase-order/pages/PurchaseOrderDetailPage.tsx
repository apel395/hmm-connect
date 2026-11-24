import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Loading from "@/components/ui/Loading";
import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import useAuthorization from "@/hooks/useAuthorization";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";
import ReceiveGoodsDialog from "@/modules/purchasing/goods-receipts/components/ReceiveGoodsDialog";
import { useGoodsReceipts } from "@/modules/purchasing/goods-receipts/hooks/useGoodsReceipts";
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
import GoodsReceiptHistory from "../components/GoodsReceiptHistory";
import PurchaseOrderForm from "../components/PurchaseOrderForm";
import {
  useApprovePurchaseOrder,
  usePurchaseOrder,
  useRejectPurchaseOrder,
  useReopenPurchaseOrder,
  useSubmitPurchaseOrder,
  useUpdatePurchaseOrder,
} from "../hooks/usePurchaseOrders";
import type { ApprovalHistoryItem, PurchaseOrderItem } from "../types";

const money = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

const taxBadge = (item: any) => {
  const category = String(item.tax_category ?? "").toUpperCase();
  if (category === "REVIEW_REQUIRED") return <Badge variant="warning">Tax Review</Badge>;
  if (item.is_taxable) return <Badge variant="info">PPN {Number(item.tax_rate ?? 0)}%</Badge>;
  return <Badge variant="secondary">Non-PPN</Badge>;
};

const sourceLabel = (type?: string) =>
  type === "FROM_PR" ? "From PR" : type === "FROM_MARKET_LIST" ? "From Market List" : "Direct";

export default function PurchaseOrderDetailPage() {
  const { id } = useParams();
  const poId = Number(id);
  const { data, isLoading } = usePurchaseOrder(poId);
  const { data: receipts = [] } = useGoodsReceipts(poId);
  const submit = useSubmitPurchaseOrder();
  const approve = useApprovePurchaseOrder();
  const reject = useRejectPurchaseOrder();
  const reopen = useReopenPurchaseOrder();
  const update = useUpdatePurchaseOrder();
  const { isSuperuser } = useAuthorization();
  const [receiving, setReceiving] = useState(false);
  const [editing, setEditing] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);

  if (isLoading) return <Loading />;
  if (!data) return null;

  const actions = data.allowed_actions ?? {};
  const admin = isSuperuser();
  const canEdit = Boolean(actions.can_edit);
  const canApprove = data.status === "PENDING_APPROVAL" && Boolean(actions.can_approve);
  const canReject = data.status === "PENDING_APPROVAL" && Boolean(actions.can_reject);
  const hasActiveReceiving = receipts.some(
    (receipt: any) => !["POSTED", "RETURNED", "CANCELLED", "VOID"].includes(String(receipt.status ?? "").toUpperCase()),
  );
  const baseCanReceive = admin ? ["APPROVED", "PARTIALLY_RECEIVED"].includes(data.status) : Boolean(actions.can_receive);
  const canReceive = baseCanReceive && !hasActiveReceiving;
  const canReopen = admin && data.status !== "DRAFT" && Boolean((actions as any).can_reopen ?? true);
  const canPrint = actions.can_print !== false;

  const subtotal = Number(
    (data as any).subtotal ??
      data.items.reduce(
        (sum: number, item: any) => sum + Number(item.line_subtotal ?? item.quantity * item.unit_price),
        0,
      ),
  );
  const discount = Number((data as any).discount_amount ?? 0);
  const taxAmount = Number(
    (data as any).tax_amount ??
      data.items.reduce((sum: number, item: any) => sum + Number(item.tax_amount ?? 0), 0),
  );
  const grandTotal = Number(data.total_amount ?? subtotal - discount + taxAmount);

  async function run(action: "submit" | "approve") {
    try {
      if (action === "submit") await submit.mutateAsync(data.id);
      if (action === "approve") await approve.mutateAsync({ id: data.id, comment: "Approved" });
      toast.success(action === "submit" ? "Purchase order submitted." : "Purchase order approval step completed.");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message ?? `${action} failed.`);
    }
  }

  async function submitRejection(comment: string) {
    await reject.mutateAsync({ id: data.id, comment });
    setRejectOpen(false);
    toast.success("Purchase order rejected.");
  }

  async function reopenForCorrection() {
    if (!window.confirm("Reopen this purchase order for correction? It will return to Draft and require approval again.")) return;
    try {
      await reopen.mutateAsync(data.id);
      toast.success("Purchase order reopened. You can edit it now and submit it for approval again.");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message ?? "Purchase order could not be reopened.");
    }
  }

  const headerActions = (
    <>
      <WorkspaceBackButton />
      {canPrint && (
        <PrintPreviewButton
          src={`/purchase-orders/${data.id}/print`}
          title={`Purchase Order ${data.po_number}`}
          ariaLabel="Preview purchase order"
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
      {actions.can_submit && <Button loading={submit.isPending} onClick={() => run("submit")}>Submit</Button>}
      {canApprove && (
        <Button variant="success" loading={approve.isPending} onClick={() => run("approve")}>
          Approve
        </Button>
      )}
      {canReceive && <Button onClick={() => setReceiving(true)}>Create RR</Button>}
    </>
  );

  return (
    <div className="space-y-5 pb-6">
      <PurchasingDocumentHeader
        eyebrow="Purchase Order"
        number={data.po_number}
        status={data.status}
        actions={headerActions}
        meta={
          <>
            <span>Supplier: <strong className="font-semibold text-slate-700">{data.supplier_name ?? "—"}</strong></span>
            <span>Source: <strong className="font-semibold text-slate-700">{sourceLabel(data.creation_type)}</strong></span>
            <span>Order date: <strong className="font-semibold text-slate-700">{data.order_date ?? "—"}</strong></span>
          </>
        }
      >
        <PurchasingMetaGrid>
          <PurchasingMetaItem label="Business Unit">{(data as any).business_unit_name ?? "—"}</PurchasingMetaItem>
          <PurchasingMetaItem label="Department">{data.department_name ?? "—"}</PurchasingMetaItem>
          <PurchasingMetaItem label="Location">{data.location_name ?? "—"}</PurchasingMetaItem>
          <PurchasingMetaItem label="Estimated Delivery">{data.expected_date ?? "—"}</PurchasingMetaItem>
          {(data.source_pr_id || data.market_list_id) && (
            <PurchasingMetaItem label="Source Document" className="col-span-2 sm:col-span-3 lg:col-span-4 xl:col-span-6">
              <div className="flex flex-wrap gap-x-6 gap-y-1">
                {data.source_pr_id && (
                  <Link className="font-medium text-emerald-700 hover:underline" to={`/purchase-requisitions/${data.source_pr_id}`}>
                    {data.source_pr_number ?? `PR #${data.source_pr_id}`}
                  </Link>
                )}
                {data.market_list_id && (
                  <Link className="font-medium text-emerald-700 hover:underline" to={`/market-lists/${data.market_list_id}`}>
                    {data.source_market_list_number ?? `ML #${data.market_list_id}`}
                  </Link>
                )}
              </div>
            </PurchasingMetaItem>
          )}
        </PurchasingMetaGrid>
      </PurchasingDocumentHeader>

      <RejectDialog
        open={rejectOpen}
        pending={reject.isPending}
        title="Reject Purchase Order"
        onClose={() => setRejectOpen(false)}
        onReject={submitRejection}
      />

      <PurchasingSection title="Order Items" flush>
        <div className="overflow-x-auto">
          <table className="purchasing-document-table min-w-[1180px]">
            <thead>
              <tr>
                <th className="text-left">Item</th>
                <th>UOM</th>
                <th className="pd-amount">Ordered</th>
                <th className="pd-amount">Received</th>
                <th className="pd-amount">Remaining</th>
                <th className="pd-amount">Unit Price</th>
                <th className="pd-amount">Subtotal</th>
                <th>Tax</th>
                <th className="pd-amount">PPN</th>
                <th className="pd-amount">Line Total</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item: PurchaseOrderItem & any) => {
                const lineSubtotal = Number(item.line_subtotal ?? Number(item.quantity) * Number(item.unit_price));
                const lineTax = Number(item.tax_amount ?? 0);
                const remaining = Number(item.remaining_quantity ?? Number(item.quantity) - Number(item.received_quantity ?? 0));
                return (
                  <tr key={item.id}>
                    <td className="pd-primary-cell">
                      <div className="pd-strong">{item.product_name}</div>
                      <div className="pd-subtext">{item.product_code}</div>
                    </td>
                    <td>{item.uom ?? "—"}</td>
                    <td className="pd-amount">{item.quantity}</td>
                    <td className="pd-amount">{item.received_quantity}</td>
                    <td className="pd-amount">{remaining}</td>
                    <td className="pd-amount">{money(item.unit_price)}</td>
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
            { label: "Discount", value: `- ${money(discount)}` },
            { label: "PPN", value: money(taxAmount) },
            { label: "Grand Total", value: money(grandTotal), emphasis: true },
          ]}
        />
      </PurchasingSection>

      <PurchasingNote>{data.notes}</PurchasingNote>

      <PurchasingSection title="Approval Progress" description="Decision history for this purchase order.">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {data.approval_history?.map((step: ApprovalHistoryItem) => (
            <div key={step.level} className="rounded-xl border border-slate-200 p-4">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <span className="font-medium">{step.level}. {step.name}</span>
                <PurchasingStatusBadge value={step.status} />
              </div>
              <div className="mt-2 text-sm text-slate-600">{step.approver_name ?? step.approver_role}</div>
              {step.decided_at && (
                <div className="mt-1 text-xs text-slate-500">{new Date(step.decided_at).toLocaleString()}</div>
              )}
              {step.comment && <p className="mt-2 text-sm text-slate-700">{step.comment}</p>}
            </div>
          ))}
        </div>
      </PurchasingSection>

      {editing && (
        <PurchaseOrderForm
          open
          initialData={data}
          loading={update.isPending}
          onClose={() => setEditing(false)}
          onSubmit={async (payload) => {
            try {
              await update.mutateAsync({ id: data.id, payload });
              setEditing(false);
              toast.success("Purchase order updated.");
            } catch (error: any) {
              const detail = error?.response?.data?.detail;
              toast.error(typeof detail === "string" ? detail : detail?.message ?? "Purchase order could not be updated.");
              throw error;
            }
          }}
        />
      )}

      <GoodsReceiptHistory purchaseOrderId={data.id} />
      {actions.can_manage_attachments !== false && (
        <DocumentAttachments entityType="PURCHASE_ORDER" entityId={data.id} />
      )}
      {actions.can_view_history !== false && <DocumentActivity events={data.activity_history} />}
      <ReceiveGoodsDialog open={receiving} purchaseOrder={data} onClose={() => setReceiving(false)} />
    </div>
  );
}
