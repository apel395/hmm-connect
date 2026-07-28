import Badge from "@/components/ui/Badge";
import Card from "@/components/ui/Card";

interface Props {
  document: any;
  approval?: any;
}

function badgeVariant(status?: string) {

  switch (
    (status ?? "")
      .toUpperCase()
  ) {

    case "APPROVED":

      return "success";

    case "PENDING":

    case "SUBMITTED":

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

function formatDate(
  value?: string,
) {

  if (!value) {

    return "-";

  }

  return new Date(
    value,
  ).toLocaleDateString();

}

export default function WorkflowHeader({

  document,

  approval,

}: Props) {

  return (

    <Card>

      <div className="grid grid-cols-2 gap-6 lg:grid-cols-4">

        <div>

          <div className="text-sm text-slate-500">

            PR Number

          </div>

          <div className="mt-1 font-semibold">

            {document.pr_number}

          </div>

        </div>

        <div>

          <div className="text-sm text-slate-500">

            Request Date

          </div>

          <div className="mt-1">

            {formatDate(
              document.request_date,
            )}

          </div>

        </div>

        <div>

          <div className="text-sm text-slate-500">

            Requester

          </div>

          <div className="mt-1">

            {document.requester_name ??
              "-"}

          </div>

        </div>

        <div>

          <div className="text-sm text-slate-500">

            Status

          </div>

          <div className="mt-1">

            <Badge

              variant={badgeVariant(
                document.status,
              )}

            >

              {document.status}

            </Badge>

          </div>

        </div>

        <div>

          <div className="text-sm text-slate-500">

            Workflow

          </div>

          <div className="mt-1">

            <Badge

              variant={badgeVariant(
                approval?.status,
              )}

            >

              {approval?.status ??
                "N/A"}

            </Badge>

          </div>

        </div>

        <div>

          <div className="text-sm text-slate-500">

            Current Approver

          </div>

          <div className="mt-1">

            {approval?.current_approver_role ??
              "-"}

          </div>

        </div>

        <div>

          <div className="text-sm text-slate-500">

            Total Items

          </div>

          <div className="mt-1">

            {document.items?.length ??
              0}

          </div>

        </div>

        <div>

          <div className="text-sm text-slate-500">

            Estimated Total

          </div>

          <div className="mt-1 font-semibold">

            {Number(
              document.total_amount ??
              0,
            ).toLocaleString(
              undefined,
              {

                minimumFractionDigits: 2,

                maximumFractionDigits: 2,

              },

            )}

          </div>

        </div>

      </div>

    </Card>

  );

}