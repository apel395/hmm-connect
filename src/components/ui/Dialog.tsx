import { ReactNode } from "react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import clsx from "clsx";

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
export const DialogDescription =
  DialogPrimitive.Description;

export interface DialogOverlayProps {
  className?: string;
}

export function DialogOverlay({
  className,
}: DialogOverlayProps) {
  return (
    <DialogPrimitive.Overlay
      className={clsx(
        "fixed inset-0 z-50 bg-black/50 backdrop-blur-sm",
        className
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
        className={clsx(
          "fixed left-1/2 top-1/2 z-50",
          "w-[95vw] max-w-2xl",
          "-translate-x-1/2 -translate-y-1/2",
          "rounded-xl border border-slate-200 bg-white shadow-2xl",
          "focus:outline-none",
          className
        )}
        onEscapeKeyDown={() => {}}
        onPointerDownOutside={() => {}}
      >
        <DialogPrimitive.Close asChild>
          <button
            type="button"
            className="absolute right-4 top-4 rounded-md p-2 text-slate-500 transition hover:bg-slate-100 hover:text-slate-900"
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
    <div
      className={clsx(
        "border-b border-slate-200 px-6 py-4",
        className
      )}
    >
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
    <div
      className={clsx(
        "px-6 py-5",
        className
      )}
    >
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
    <div
      className={clsx(
        "flex items-center justify-end gap-3 border-t border-slate-200 px-6 py-4",
        className
      )}
    >
      {children}
    </div>
  );
}