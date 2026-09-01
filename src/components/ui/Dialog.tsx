import { ReactNode } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import clsx from "clsx";
import { FORM_UI } from "@/config/formUi";

export interface DialogProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children: ReactNode;
}

export default function Dialog({
  children,
  open,
  defaultOpen,
  onOpenChange,
}: DialogProps) {
  return (
    <DialogPrimitive.Root
      open={open}
      defaultOpen={defaultOpen}
      onOpenChange={onOpenChange}
    >
      {children}
    </DialogPrimitive.Root>
  );
}

export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogPortal = DialogPrimitive.Portal;
export const DialogTitle = DialogPrimitive.Title;
export const DialogDescription = DialogPrimitive.Description;

export interface DialogOverlayProps {
  className?: string;
}

export function DialogOverlay({ className }: DialogOverlayProps) {
  return (
    <DialogPrimitive.Overlay
      className={clsx(
        "fixed inset-0 z-50 bg-slate-950/55 backdrop-blur-[1px]",
        className,
      )}
    />
  );
}

export interface DialogContentProps {
  children: ReactNode;
  className?: string;
}

export function DialogContent({
  children,
  className,
}: DialogContentProps) {
  return (
    <DialogPortal>
      <DialogOverlay />
      <DialogPrimitive.Content
        role="dialog"
        className={clsx(
          "fixed left-1/2 top-1/2 z-50",
          "flex max-h-[calc(100vh-2rem)] w-[95vw] max-w-2xl flex-col overflow-hidden",
          "[&>form]:flex [&>form]:min-h-0 [&>form]:flex-1 [&>form]:flex-col [&>form]:overflow-hidden",
          "-translate-x-1/2 -translate-y-1/2",
          "rounded-xl border border-slate-200 bg-white shadow-2xl",
          "focus:outline-none",
          className,
        )}
      >
        <DialogPrimitive.Close asChild>
          <button
            type="button"
            className="absolute right-3 top-3 rounded-md p-1.5 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900 focus:outline-none focus:ring-2 focus:ring-blue-500/30"
            aria-label="Close"
          >
            <X className="h-5 w-5" />
          </button>
        </DialogPrimitive.Close>
        {children}
      </DialogPrimitive.Content>
    </DialogPortal>
  );
}

export interface DialogHeaderProps {
  children?: ReactNode;
  className?: string;
}

export function DialogHeader({
  children,
  className,
}: DialogHeaderProps) {
  return (
    <div className={clsx(FORM_UI.dialog.header, className)}>
      {children}
    </div>
  );
}

export interface DialogBodyProps {
  children?: ReactNode;
  className?: string;
}

export function DialogBody({
  children,
  className,
}: DialogBodyProps) {
  return (
    <div className={clsx(FORM_UI.dialog.body, className)}>
      {children}
    </div>
  );
}

export interface DialogFooterProps {
  children?: ReactNode;
  className?: string;
}

export function DialogFooter({
  children,
  className,
}: DialogFooterProps) {
  return (
    <div className={clsx(FORM_UI.dialog.footer, className)}>
      {children}
    </div>
  );
}
