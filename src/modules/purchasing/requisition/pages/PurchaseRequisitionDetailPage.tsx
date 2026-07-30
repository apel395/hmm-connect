import {
  useNavigate,
  useParams,
} from "react-router-dom";

import { toast } from "sonner";

import PageHeader from "@/components/common/PageHeader";

import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Loading from "@/components/ui/Loading";

import useAuthStore from "@/store/auth";

import WorkflowHeader from "../components/WorkflowHeader";
import WorkflowActionBar from "../components/WorkflowActionBar";
import ApprovalSummary from "../components/ApprovalSummary";

import {
  usePurchaseRequisition,
  useSubmitPurchaseRequisition,
  useApprovePurchaseRequisition,
  useRejectPurchaseRequisition,
} from "../hooks/usePurchaseRequisitions";

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

  const user =
    useAuthStore(
      (
        state: any,
      ) => state.user,
    );

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

  const workflowStatus =
    approval?.status?.toUpperCase();

  const currentRole =
    approval?.current_approver_role;

  const documentStatus =
    data.status?.toUpperCase();

  const userRoles =
    (
      user?.roles ?? []
    ).map(
      (
        role: any,
      ) =>
        role.name?.toUpperCase(),
    );

  const isAdmin =
    userRoles.includes(
      "ADMIN",
    );

  const isCurrentApprover =
    isAdmin ||

    (
      currentRole &&

      userRoles.includes(
        currentRole.toUpperCase(),
      )

    );

  const canSubmit =
    documentStatus ===
    "DRAFT";

  const canApprove =
    documentStatus ===
      "PENDING_APPROVAL" &&
    workflowStatus ===
      "PENDING" &&
    isCurrentApprover;

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

        onApprove={
          handleApprove
        }

        onReject={
          handleReject
        }

      />

      <div className="grid grid-cols-12 gap-6">

        <div className="col-span-8 space-y-6">

          <Card className="overflow-hidden p-0">

            <div className="border-b border-slate-200 bg-slate-50 px-6 py-4">

              <h2 className="font-semibold">

                Requisition Items

              </h2>

            </div>

            <div className="overflow-x-auto">

              <table className="min-w-full text-sm">

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

    </div>

  );

}