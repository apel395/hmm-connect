import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import { ArrowLeft } from "lucide-react";

interface Props {
  document: any;
  approval?: any;
  canSubmit: boolean;
  canApprove: boolean;
  canReject: boolean;
  canEdit: boolean;
  canPrint: boolean;
  printSrc?: string;
  printTitle?: string;
  submitting?: boolean;
  approving?: boolean;
  rejecting?: boolean;
  onBack: () => void;
  onSubmit: () => void;
  onEdit: () => void;
  onApprove: () => void;
  onReject: () => void;
}

export default function WorkflowActionBar({
  document,
  approval,
  canSubmit,
  canApprove,
  canReject,
  canEdit,
  canPrint,
  printSrc,
  printTitle,
  submitting = false,
  approving = false,
  rejecting = false,
  onBack,
  onSubmit,
  onEdit,
  onApprove,
  onReject,
}: Props) {
  const pendingStep = approval?.steps?.find((step: any) => step.status === "PENDING");
  const currentRole =
    approval?.current_approver_role ??
    pendingStep?.approver_role_name ??
    pendingStep?.name ??
    "-";
  const defaultNumber = document.pr_number ?? document.ml_number ?? "";
  const resolvedPrintSrc = printSrc ?? `/purchase-requisitions/${document.id}/print`;
  const resolvedPrintTitle = printTitle ?? `Purchase Requisition ${defaultNumber}`;

  return (
    <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
      <div className="flex flex-wrap gap-3">
        <Button variant="outline" onClick={onBack}><ArrowLeft size={17}/> Back</Button>
        {canPrint && <PrintPreviewButton src={resolvedPrintSrc} title={resolvedPrintTitle} ariaLabel={`Preview ${resolvedPrintTitle}`} />}
        {canEdit && <Button variant="outline" onClick={onEdit}>Edit</Button>}
        {canSubmit && <Button loading={submitting} onClick={onSubmit}>Submit</Button>}
        {canReject && <Button variant="danger" loading={rejecting} onClick={onReject}>Reject</Button>}
        {canApprove && <Button variant="success" loading={approving} onClick={onApprove}>Approve</Button>}
        <div className="ml-auto flex items-center rounded-lg border border-slate-200 bg-slate-50 px-4 py-2 text-sm text-slate-600">
          Current Approver <span className="ml-2 font-semibold text-slate-900">{currentRole}</span>
        </div>
      </div>
    </div>
  );
}
