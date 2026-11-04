import type { ReactNode } from "react";
import clsx from "clsx";
import Dialog, {
  DialogBody,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";

type FormDialogSize = "standard" | "wide" | "large" | "extra";

interface FormDialogProps {
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  footer: ReactNode;
  onRequestClose: () => void;
  busy?: boolean;
  size?: FormDialogSize;
  bodyClassName?: string;
}

const sizes: Record<FormDialogSize, string> = {
  standard: "max-w-2xl",
  wide: "max-w-4xl",
  large: "max-w-6xl",
  extra: "max-w-[1440px]",
};

export default function FormDialog({
  open,
  title,
  description,
  children,
  footer,
  onRequestClose,
  busy = false,
  size = "wide",
  bodyClassName,
}: FormDialogProps) {
  return (
    <Dialog
      open={open}
      onOpenChange={(next) => !next && !busy && onRequestClose()}
    >
      <DialogContent
        closeButtonDisabled={busy}
        className={clsx("max-h-[min(92dvh,900px)]", sizes[size])}
      >
        <DialogHeader>
          <DialogTitle className="text-base font-semibold text-slate-900">
            {title}
          </DialogTitle>
          {description && (
            <DialogDescription className="mt-1 text-xs text-slate-500">
              {description}
            </DialogDescription>
          )}
        </DialogHeader>
        <DialogBody
          className={clsx("min-h-0 flex-1 overscroll-contain", bodyClassName)}
        >
          {children}
        </DialogBody>
        <DialogFooter>{footer}</DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
