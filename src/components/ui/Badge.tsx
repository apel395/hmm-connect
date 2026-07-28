import { HTMLAttributes } from "react";
import clsx from "clsx";

export type BadgeVariant =
  | "default"
  | "primary"
  | "success"
  | "warning"
  | "danger"
  | "info"
  | "outline";

export interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement> {
  variant?: BadgeVariant;
}

const variants: Record<BadgeVariant, string> = {
  default: "bg-slate-100 text-slate-700",
  primary: "bg-blue-100 text-blue-700",
  success: "bg-emerald-100 text-emerald-700",
  warning: "bg-amber-100 text-amber-700",
  danger: "bg-red-100 text-red-700",
  info: "bg-cyan-100 text-cyan-700",
  outline: "border border-slate-300 bg-white text-slate-700",
};

export default function Badge({
  variant = "default",
  className,
  children,
  ...props
}: BadgeProps) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold",
        variants[variant],
        className
      )}
      {...props}
    >
      {children}
    </span>
  );
}
