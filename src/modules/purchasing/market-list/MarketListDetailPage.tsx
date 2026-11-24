import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import useAuthorization from "@/hooks/useAuthorization";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import DocumentActivity from "../components/DocumentActivity";
import RejectDialog from "../components/RejectDialog";
import {
  PurchasingDocumentHeader,
  PurchasingMetaGrid,
  PurchasingMetaItem,
  PurchasingNote,
  PurchasingSection,
  PurchasingStatusBadge,
  PurchasingTotals,
} from "../components/PurchasingDocumentUI";
import ApprovalSummary from "../requisition/components/ApprovalSummary";
import { useApproval } from "../requisition/hooks/useApprovals";
import MarketListConvertDialog from "./MarketListConvertDialog";
import MarketListForm from "./MarketListForm";
import {
  useApproveMarketList,
  useConvertMarketList,
  useMarketList,
  useRejectMarketList,
  useReopenMarketList,
  useSubmitMarketList,
  useUpdateMarketList,
} from "./useMarketLists";

const money = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export default function MarketListDetailPage() {
  const id = Number(useParams().id);
  const nav = useNavigate();
  const query = useMarketList(id);
  const approvalQuery = useApproval("MARKET_LIST", id);
  const submit = useSubmitMarketList();
  const approve = useApproveMarketList();
  const reject = useRejectMarketList();
  const reopen = useReopenMarketList();
  const update = useUpdateMarketList();
  const convert = useConvertMarketList();
  const { hasPermission } = useAuthorization();
  const [editing, setEditing] = useState(false);
  const [rejectOpen, setRejectOpen] = useState(false);
  const [convertOpen, setConvertOpen] = useState(false);
  const data: any = query.data;

  if (query.isLoading) return <Loading />;
  if (!data) return <Card>Market List could not be loaded.</Card>;

  const approval = approvalQuery.data;
  const pending = data.status === "PENDING_APPROVAL" && approval?.status === "PENDING";
  const canSubmit = hasPermission("market_list.submit") && data.status === "DRAFT" && Boolean(data.allowed_actions?.can_submit);
  const canApprove = hasPermission("market_list.approve") && pending && Boolean(approval?.can_decide);
  const canReject = hasPermission("market_list.approve") && pending && Boolean(approval?.can_decide);
  const canEdit = hasPermission("market_list.edit") && data.status === "DRAFT" && Boolean(data.allowed_actions?.can_edit);
  const canReopen = Boolean(data.allowed_actions?.can_reopen);
  const canConvert = hasPermission("market_list.convert") && data.status === "APPROVED";
  const canPrint = data.allowed_actions?.can_print !== false;

  const act = async (kind: "submit" | "approve") => {
    try {
      if (kind === "submit") await submit.mutateAsync(id);
      if (kind === "approve") await approve.mutateAsync({ id, comment: "Approved" });
      toast.success(kind === "submit" ? "Market List submitted." : "Approval completed.");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message ?? `${kind} failed.`);
    }
  };

  const submitRejection = async (comment: string) => {
    await reject.mutateAsync({ id, comment });
    setRejectOpen(false);
    toast.success("Market List rejected.");
  };

  const reopenForCorrection = async () => {
    try {
      await reopen.mutateAsync(id);
      toast.success("Market List reopened.");
    } catch (error: any) {
      const detail = error?.response?.data?.detail;
      toast.error(typeof detail === "string" ? detail : detail?.message ?? "Market List could not be reopened.");
    }
  };

  const actions = (
    <>
      <WorkspaceBackButton />
      {canPrint && (
        <PrintPreviewButton
          src={`/market-lists/${id}/print`}
          title={`Market List ${data.ml_number}`}
          ariaLabel="Preview market list"
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
      {canConvert && <Button onClick={() => setConvertOpen(true)}>Create Purchase Order</Button>}
    </>
  );

  return (
    <div className="space-y-5 pb-6">
      <PurchasingDocumentHeader
        eyebrow="Market List"
        number={data.ml_number}
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
          <PurchasingMetaItem label="Current Approver">{approval?.current_approver_role ?? "—"}</PurchasingMetaItem>
        </PurchasingMetaGrid>
      </PurchasingDocumentHeader>

      <RejectDialog
        open={rejectOpen}
        pending={reject.isPending}
        title="Reject Market List"
        onClose={() => setRejectOpen(false)}
        onReject={submitRejection}
      />

      {convertOpen && (
        <MarketListConvertDialog
          open
          marketList={data}
          onClose={() => setConvertOpen(false)}
          onConvert={async (items, supplierId) => {
            const response = await convert.mutateAsync({ id, supplier_id: supplierId, items });
            setConvertOpen(false);
            toast.success("Purchase Order created.");
            nav(`/purchase-orders/${response.data.id}`);
          }}
        />
      )}

      <div className="grid gap-5 lg:grid-cols-12">
        <div className="space-y-5 lg:col-span-8">
          <PurchasingSection title="Market Items" flush>
            <div className="overflow-x-auto">
              <table className="purchasing-document-table min-w-[880px]">
                <thead>
                  <tr>
                    <th className="text-left">Item</th>
                    <th>UOM</th>
                    <th className="pd-amount">Qty</th>
                    <th className="pd-amount">Estimated Price</th>
                    <th>Tax</th>
                    <th className="pd-amount">PPN</th>
                    <th className="pd-amount">Line Total</th>
                  </tr>
                </thead>
                <tbody>
                  {(data.items ?? []).map((item: any) => (
                    <tr key={item.id}>
                      <td className="pd-primary-cell">
                        <div className="pd-strong">{item.product_name}</div>
                        <div className="pd-subtext">{item.product_code}</div>
                      </td>
                      <td>{item.uom ?? "—"}</td>
                      <td className="pd-amount">{item.quantity}</td>
                      <td className="pd-amount">{money(item.estimated_price)}</td>
                      <td>{item.is_taxable ? `PPN ${Number(item.tax_rate ?? 0)}%` : "Non-PPN"}</td>
                      <td className="pd-amount">{money(item.tax_amount)}</td>
                      <td className="pd-amount pd-strong">{money(item.line_total)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <PurchasingTotals
              rows={[
                { label: "Subtotal", value: money(data.subtotal) },
                { label: "PPN", value: money(data.tax_amount) },
                { label: "Grand Total", value: money(data.total_amount), emphasis: true },
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
                <span className="text-slate-500">ML Number</span>
                <span className="font-medium">{data.ml_number}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-slate-500">Total Items</span>
                <span className="font-medium">{data.items?.length ?? 0}</span>
              </div>
              <div className="flex justify-between gap-4">
                <span className="text-slate-500">Grand Total</span>
                <span className="font-semibold tabular-nums">{money(data.total_amount)}</span>
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
        <MarketListForm
          initialData={data}
          onClose={() => setEditing(false)}
          onSubmit={async (payload) => {
            await update.mutateAsync({ id, payload });
            setEditing(false);
          }}
        />
      )}

      <DocumentAttachments entityType="MARKET_LIST" entityId={id} />
      <DocumentActivity events={data.activity_history} />
    </div>
  );
}
