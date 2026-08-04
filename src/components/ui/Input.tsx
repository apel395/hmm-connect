import { forwardRef, InputHTMLAttributes } from "react";
import clsx from "clsx";

export interface InputProps
  extends InputHTMLAttributes<HTMLInputElement> {
  error?: boolean;
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, error = false, disabled, ...props }, ref) => {
    return (
      <input
        ref={ref}
        disabled={disabled}
        className={clsx(
          "flex h-9 w-full rounded-md border bg-white px-3 py-2 text-[13px]",
          "placeholder:text-slate-400",
          "focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-blue-500",
          "disabled:cursor-not-allowed disabled:bg-slate-100 disabled:opacity-60",
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

Input.displayName = "Input";

export default Input;
