import {
  useNavigate,
  useParams,
  Link,
} from "react-router-dom";

import { toast } from "sonner";

import PageHeader from "@/components/common/PageHeader";

import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Loading from "@/components/ui/Loading";
import Button from "@/components/ui/Button";

import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";

import WorkflowHeader from "../components/WorkflowHeader";
import WorkflowActionBar from "../components/WorkflowActionBar";
import ApprovalSummary from "../components/ApprovalSummary";

import {
  usePurchaseRequisition,
  useSubmitPurchaseRequisition,
  useApprovePurchaseRequisition,
  useRejectPurchaseRequisition,
  useUpdatePurchaseRequisition,
} from "../hooks/usePurchaseRequisitions";
import { useState } from "react";
import Input from "@/components/ui/Input";
import DocumentActivity from "../../components/DocumentActivity";

import {
  useApproval,
} from "../hooks/useApprovals";

function formatMoney(
  value: any,
) {

  return Number(
    value ?? 0,
  ).toLocaleString(
    undefined,
    {

      minimumFractionDigits: 2,

      maximumFractionDigits: 2,

    },
  );

}

function badgeVariant(
  status?: string,
) {

  switch (
    (
      status ??
      ""
    ).toUpperCase()
  ) {

    case "APPROVED":

      return "success";

    case "PENDING":
      return "warning";

    case "SUBMITTED":
      return "warning";

    case "PENDING_APPROVAL":
      return "warning";

    case "REJECTED":

      return "danger";

    case "CANCELLED":

      return "secondary";

    default:

      return "outline";

  }

}

export default function PurchaseRequisitionDetailPage() {

  const navigate =
    useNavigate();

  const {
    id,
  } = useParams();

  const prId =
    Number(id);

  const {
    data,
    isLoading,
  } =
    usePurchaseRequisition(
      prId,
    );

  const {
    data: approval,
    isLoading:
      approvalLoading,
  } =
    useApproval(
      "PURCHASE_REQUISITION",
      prId,
    );

  const submit =
    useSubmitPurchaseRequisition();

  const approve =
    useApprovePurchaseRequisition();

  const reject =
    useRejectPurchaseRequisition();
  const update = useUpdatePurchaseRequisition();
  const [editing, setEditing] = useState(false);
  const [notes, setNotes] = useState("");

  if (

    isLoading ||

    approvalLoading

  ) {

    return (

      <div className="py-24">

        <Loading />

      </div>

    );

  }

  if (
    !data
  ) {

    return null;

  }

  const canSubmit = data.allowed_actions?.can_submit ?? false;

  const canApprove = data.allowed_actions?.can_approve ?? false;
  const canReject = data.allowed_actions?.can_reject ?? false;

  const grandTotal =
  (data?.items ?? []).reduce(
    (sum: number, item: any) =>
      sum +
      Number(
        item.total_price ??
        item.quantity * item.estimated_price,
      ),
    0,
  );

  async function handleSubmit() {

    try {

      await submit.mutateAsync(
        data.id,
      );

      toast.success(
        "Purchase Requisition submitted.",
      );

    } catch (
      e: any
    ) {

      toast.error(

        e?.response?.data?.detail ??

        "Unable to submit.",

      );

    }

  }

  async function handleApprove() {

    try {

      await approve.mutateAsync({

        id:
          data.id,

        comment:
          "Approved",

      });

      toast.success(
        "Approval completed.",
      );

      navigate(
        "/purchase-requisitions",
      );

    } catch (
      e: any
    ) {

      toast.error(

        e?.response?.data?.detail ??

        "Approval failed.",

      );

    }

  }

  async function handleReject() {

    try {

      await reject.mutateAsync({

        id:
          data.id,

        comment:
          "Rejected",

      });

      toast.success(
        "Document rejected.",
      );

      navigate(
        "/purchase-requisitions",
      );

    } catch (
      e: any
    ) {

      toast.error(

        e?.response?.data?.detail ??

        "Reject failed.",

      );

    }

  }
    return (

    <div className="space-y-6">

      <PageHeader

        title={
          data.pr_number
        }

        description="Purchase Requisition"

        actions={

          <div className="flex items-center gap-3">

            <Badge

              variant={
                badgeVariant(
                  data.status,
                )
              }

            >

              {data.status}

            </Badge>

          </div>

        }

      />

      <WorkflowHeader

        document={
          data
        }

        approval={
          approval
        }

      />

      <WorkflowActionBar

        document={
          data
        }

        approval={
          approval
        }

        canSubmit={
          canSubmit
        }

        canApprove={
          canApprove
        }
        canReject={canReject}
        canEdit={data.allowed_actions?.can_edit ?? false}
        canPrint={data.allowed_actions?.can_print !== false}

        submitting={
          submit.isPending
        }

        approving={
          approve.isPending
        }

        rejecting={
          reject.isPending
        }

        onBack={() =>
          navigate(
            "/purchase-requisitions",
          )
        }

        onSubmit={
          handleSubmit
        }
        onEdit={() => { setNotes(data.notes ?? ""); setEditing(true); }}

        onApprove={
          handleApprove
        }

        onReject={
          handleReject
        }

      />

      {editing && <Card><h2 className="mb-4 font-semibold">Edit Purchase Requisition</h2><label className="text-sm font-medium">Notes<Input value={notes} onChange={(event) => setNotes(event.target.value)}/></label><div className="mt-4 flex justify-end gap-2"><Button variant="outline" onClick={() => setEditing(false)}>Cancel</Button><Button loading={update.isPending} onClick={async () => { await update.mutateAsync({ id: data.id, data: { request_date: data.request_date, expiry_date: data.expiry_date ?? null, notes, items: data.items.map((item: any) => ({ product_id: item.product_id, quantity: Number(item.quantity), estimated_price: Number(item.estimated_price) })) } }); setEditing(false); toast.success("Purchase requisition updated."); }}>Save</Button></div></Card>}

      <div className="grid grid-cols-12 gap-6">

        <div className="col-span-8 space-y-6">

          <Card className="overflow-hidden p-0">

            <div className="border-b border-slate-200 bg-slate-50 px-6 py-4">

              <h2 className="font-semibold">

                Requisition Items

              </h2>

            </div>

            <div className="overflow-x-auto">

              <table className="table-grid min-w-full text-sm">

                <thead className="bg-slate-100">

                  <tr>

                    <th className="px-5 py-3 text-left">

                      Product

                    </th>

                    <th className="w-24 px-5 py-3 text-right">

                      Qty

                    </th>

                    <th className="w-40 px-5 py-3 text-right">

                      Estimated Price

                    </th>

                    <th className="w-40 px-5 py-3 text-right">

                      Total

                    </th>

                  </tr>

                </thead>

                <tbody>

                  {(data.items ?? []).map(

                    (
                      item: any,
                      index: number,
                    ) => (

                      <tr

                        key={
                          item.id ??
                          index
                        }

                        className="border-t border-slate-200"

                      >

                        <td className="px-5 py-4">

                          <div className="font-medium">

                            {item.product_name}

                          </div>

                          <div className="text-xs text-slate-500">

                            {item.product_code}

                          </div>

                        </td>

                        <td className="px-5 py-4 text-right">

                          {item.quantity}

                        </td>

                        <td className="px-5 py-4 text-right">

                          {formatMoney(
                            item.estimated_price,
                          )}

                        </td>

                        <td className="px-5 py-4 text-right font-semibold">

                          {formatMoney(

                            item.total_price ??

                            item.quantity *

                              item.estimated_price,

                          )}

                        </td>

                      </tr>

                    ),

                  )}

                </tbody>

                <tfoot className="border-t-2 border-slate-300 bg-slate-50">

                  <tr>

                    <td

                      colSpan={3}

                      className="px-5 py-4 text-right font-semibold"

                    >

                      Grand Total

                    </td>

                    <td className="px-5 py-4 text-right text-lg font-bold">

                      {formatMoney(
                        grandTotal,
                      )}

                    </td>

                  </tr>

                </tfoot>

              </table>

            </div>

          </Card>

          <Card>

            <h3 className="mb-4 text-lg font-semibold">

              Notes

            </h3>

            <div className="rounded-md bg-slate-50 p-4">

              {data.notes ||

                "No notes provided."}

            </div>

          </Card>
                  </div>

        <div className="col-span-4 space-y-6">

          <ApprovalSummary

            approval={
              approval
            }

          />

          <Card>

            <h3 className="mb-4 text-lg font-semibold">

              Information

            </h3>

            <div className="space-y-4">
              {!!data.generated_purchase_orders?.length && <div><div className="mb-2 text-slate-500">Generated Purchase Orders</div>{data.generated_purchase_orders.map((order: { id:number; document_number:string }) => <Link key={order.id} className="mr-3 font-medium text-emerald-700 hover:underline" to={`/purchase-orders/${order.id}`}>{order.document_number}</Link>)}</div>}

              <div className="flex justify-between">

                <span className="text-slate-500">

                  PR Number

                </span>

                <span className="font-medium">

                  {data.pr_number}

                </span>

              </div>

              <div className="flex justify-between">

                <span className="text-slate-500">

                  Request Date

                </span>

                <span>

                  {data.request_date
                    ? new Date(
                        data.request_date,
                      ).toLocaleDateString()
                    : "-"}

                </span>

              </div>

              <div className="flex justify-between">

                <span className="text-slate-500">

                  Requester

                </span>

                <span>

                  {data.requester_name ??
                    "-"}

                </span>

              </div>

              <div className="flex justify-between">

                <span className="text-slate-500">

                  Status

                </span>

                <Badge

                  variant={
                    badgeVariant(
                      data.status,
                    )
                  }

                >

                  {data.status}

                </Badge>

              </div>

              <div className="flex justify-between">

                <span className="text-slate-500">

                  Total Items

                </span>

                <span>

                  {data.items?.length ??
                    0}

                </span>

              </div>

              <div className="flex justify-between border-t pt-4">

                <span className="font-semibold">

                  Total Estimate

                </span>

                <span className="text-lg font-bold">

                  {formatMoney(
                    grandTotal,
                  )}

                </span>

              </div>

            </div>

          </Card>

        </div>

      </div>

      {data.allowed_actions?.can_manage_attachments !== false && <DocumentAttachments
        entityType="PURCHASE_REQUISITION"
        entityId={data.id}
      />}
      {data.allowed_actions?.can_view_history !== false && <DocumentActivity events={data.activity_history}/>}

    </div>

  );

}
