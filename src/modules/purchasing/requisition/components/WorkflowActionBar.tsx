import Button from "@/components/ui/Button";

interface Props {
  document: any;
  approval?: any;

  canSubmit: boolean;
  canApprove: boolean;

  submitting?: boolean;
  approving?: boolean;
  rejecting?: boolean;

  onBack: () => void;
  onSubmit: () => void;
  onApprove: () => void;
  onReject: () => void;
}

export default function WorkflowActionBar({

  approval,

  canSubmit,

  canApprove,

  submitting = false,

  approving = false,

  rejecting = false,

  onBack,

  onSubmit,

  onApprove,

  onReject,

}: Props) {

  const currentRole =
    approval?.current_approver_role;

  return (

    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">

      <div className="flex flex-wrap gap-3">

        <Button

          variant="outline"

          onClick={onBack}

        >

          Back

        </Button>

        {canSubmit && (

          <Button

            loading={submitting}

            onClick={onSubmit}

          >

            Submit

          </Button>

        )}

        {canApprove && (

          <>

            <Button

              variant="success"

              loading={approving}

              onClick={onApprove}

            >

              Approve

            </Button>

            <Button

              variant="danger"

              loading={rejecting}

              onClick={onReject}

            >

              Reject

            </Button>

          </>

        )}

        <div className="ml-auto flex items-center rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-600">

          Current Approver

          <span className="ml-2 font-semibold text-slate-900">

            {currentRole ?? "-"}

          </span>

        </div>

      </div>

    </div>

  );

}