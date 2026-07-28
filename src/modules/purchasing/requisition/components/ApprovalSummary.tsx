import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";

interface Props {
  approval?: any;
}

function badgeVariant(
  status?: string,
) {

  switch (
    (status ?? "")
      .toUpperCase()
  ) {

    case "APPROVED":

      return "success";

    case "PENDING":

      return "warning";

    case "REJECTED":

      return "danger";

    case "CANCELLED":

      return "secondary";

    default:

      return "outline";

  }

}

export default function ApprovalSummary({
  approval,
}: Props) {

  const workflow =
    approval?.workflow;

  const steps =
    approval?.steps ?? [];

  return (

    <Card>

      <h3 className="mb-5 text-lg font-semibold">

        Approval Workflow

      </h3>

      <div className="space-y-4">

        <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">

          <div className="text-xs uppercase tracking-wide text-slate-500">

            Workflow

          </div>

          <div className="mt-1 font-semibold">

            {workflow?.name ?? "-"}

          </div>

        </div>

        {steps.length === 0 && (

          <div className="py-6 text-center text-sm text-slate-500">

            No approval steps.

          </div>

        )}

        {steps.map(
          (
            step: any,
            index: number,
          ) => (

            <div

              key={
                step.id ??
                index
              }

              className="rounded-lg border border-slate-200 p-4"

            >

              <div className="flex items-center justify-between">

                <div>

                  <div className="font-medium">

                    Step {step.step_order}

                  </div>

                  <div className="text-sm text-slate-500">

                    {step.approver_role_name}

                  </div>

                </div>

                <Badge

                  variant={badgeVariant(
                    step.status,
                  )}

                >

                  {step.status}

                </Badge>

              </div>

              {(step.approver_name ||
                step.action_date) && (

                <div className="mt-4 border-t pt-3 text-sm text-slate-600">

                  {step.approver_name && (

                    <div>

                      <span className="font-medium">

                        By:

                      </span>{" "}

                      {step.approver_name}

                    </div>

                  )}

                  {step.action_date && (

                    <div>

                      <span className="font-medium">

                        Date:

                      </span>{" "}

                      {new Date(
                        step.action_date,
                      ).toLocaleString()}

                    </div>

                  )}

                </div>

              )}

              {step.comment && (

                <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm text-slate-700">

                  {step.comment}

                </div>

              )}

            </div>

          ),

        )}

      </div>

    </Card>

  );

}