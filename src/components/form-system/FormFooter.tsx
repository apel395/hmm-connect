import type { ReactNode } from "react";
import Button from "@/components/ui/Button";

interface FormFooterProps {
  onCancel: () => void;
  onSubmit: () => void;
  submitLabel: string;
  saving?: boolean;
  submitDisabled?: boolean;
  aside?: ReactNode;
}

export default function FormFooter({
  onCancel,
  onSubmit,
  submitLabel,
  saving,
  submitDisabled = false,
  aside,
}: FormFooterProps) {
  return (
    <div className="flex w-full flex-wrap items-center justify-between gap-2">
      <div className="min-w-0 flex-1 text-xs text-slate-500">{aside}</div>
      <div className="flex shrink-0 items-center gap-2">
        <Button
          type="button"
          variant="outline"
          disabled={saving}
          onClick={onCancel}
        >
          Cancel
        </Button>
        <Button
          type="button"
          loading={saving}
          disabled={submitDisabled}
          onClick={onSubmit}
        >
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}
