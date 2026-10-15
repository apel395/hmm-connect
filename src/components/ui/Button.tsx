import { ButtonHTMLAttributes, Children, isValidElement, forwardRef } from "react";
import clsx from "clsx";
import { Download, Printer, RefreshCw, SlidersHorizontal } from "lucide-react";

export type ButtonVariant =
  | "primary"
  | "secondary"
  | "outline"
  | "danger"
  | "success"
  | "warning"
  | "ghost";

export type ButtonSize =
  | "xs"
  | "sm"
  | "md"
  | "lg";

export interface ButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  loading?: boolean;
}

const variantClasses: Record<ButtonVariant, string> = {
  primary:
    "bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500",

  secondary:
    "bg-slate-700 text-white hover:bg-slate-800 focus:ring-slate-500",

  outline:
    "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus:ring-slate-400",

  danger:
    "bg-red-600 text-white hover:bg-red-700 focus:ring-red-500",

  success:
    "bg-emerald-600 text-white hover:bg-emerald-700 focus:ring-emerald-500",

  warning:
    "bg-amber-500 text-white hover:bg-amber-600 focus:ring-amber-400",

  ghost:
    "bg-transparent text-slate-700 hover:bg-slate-100 focus:ring-slate-300",
};

const sizeClasses: Record<ButtonSize, string> = {
  xs: "h-7 px-2 text-[11px]",
  sm: "h-7 px-2 text-xs",
  md: "h-8 px-3 text-xs",
  lg: "h-10 px-5 text-sm",
};

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  (
    {
      variant = "primary",
      size = "md",
      loading = false,
      className,
      disabled,
      children,
      ...props
    },
    ref
  ) => {
    const nodes = Children.toArray(children);
    const supportLabel = nodes.filter(node => typeof node === "string").join(" ").trim();
    const compactSupport = /^(print(?: preview| report| complete report)?|export(?: to)?(?: excel| xlsx?| csv)?|download xlsx?|filters?(?: \(\d+\))?|refresh)$/i.test(supportLabel);
    const SupportIcon = /^print/i.test(supportLabel) ? Printer : /^filters?/i.test(supportLabel) ? SlidersHorizontal : /^refresh/i.test(supportLabel) ? RefreshCw : Download;
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={clsx(
          "inline-flex items-center justify-center gap-2 rounded-md font-medium transition",
          "focus:outline-none focus:ring-2 focus:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-60",
          variantClasses[variant],
          sizeClasses[size],
          className
        )}
        title={compactSupport ? supportLabel : undefined}
        aria-label={compactSupport ? supportLabel : undefined}
        {...props}
      >
        {loading && (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        )}

        {compactSupport ? <>{nodes.some(isValidElement) ? nodes.filter(node => typeof node !== "string") : <SupportIcon size={15}/>}<span className="sr-only">{supportLabel}</span></> : children}
      </button>
    );
  }
);

Button.displayName = "Button";

export default Button;
