import { forwardRef, TextareaHTMLAttributes } from "react";
import clsx from "clsx";

export interface TextareaProps
  extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  error?: boolean;
}

const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  (
    {
      className,
      error = false,
      disabled,
      rows = 4,
      ...props
    },
    ref
  ) => {
    return (
      <textarea
        ref={ref}
        rows={rows}
        disabled={disabled}
        className={clsx(
          "flex min-h-20 w-full rounded-md border bg-white px-3 py-2 text-[13px]",
          "placeholder:text-slate-400",
          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
          "disabled:cursor-not-allowed disabled:bg-slate-100 disabled:opacity-60",
          "resize-y",
          error
            ? "border-red-500 focus:ring-red-500 focus:border-red-500"
            : "border-slate-300",
          className
        )}
        {...props}
      />
    );
  }
);

Textarea.displayName = "Textarea";

export default Textarea;
