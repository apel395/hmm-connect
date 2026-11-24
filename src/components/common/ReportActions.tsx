import type { ReactNode } from "react";
import clsx from "clsx";
import { Download, Info } from "lucide-react";
import Button, { type ButtonSize, type ButtonVariant } from "@/components/ui/Button";
import { exportActionLabel, type ExportScope } from "./reportActionCopy";

export function ExportButton({
  scope = "page",
  format = "csv",
  label,
  onClick,
  disabled,
  loading,
  size = "sm",
  variant = "outline",
  className,
}: {
  scope?: ExportScope;
  format?: "csv" | "excel";
  label?: string;
  onClick: () => void;
  disabled?: boolean;
  loading?: boolean;
  size?: ButtonSize;
  variant?: ButtonVariant;
  className?: string;
}) {
  const text = label ?? exportActionLabel(scope, format);
  return (
    <Button
      type="button"
      size={size}
      variant={variant}
      onClick={onClick}
      disabled={disabled}
      loading={loading}
      className={className}
      title={text}
      aria-label={text}
    >
      <Download size={15} />
      <span>{text}</span>
    </Button>
  );
}

/** Short scope/template note kept beside an action, never inside print output. */
export function ReportScopeNote({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <p
      className={clsx(
        "flex items-start gap-1.5 text-[11px] leading-snug text-slate-500 print:hidden",
        className,
      )}
    >
      <Info size={13} className="mt-0.5 shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </p>
  );
}
