import { ButtonHTMLAttributes, ReactNode, forwardRef } from "react";
import clsx from "clsx";

export type IconButtonVariant =
  | "primary"
  | "secondary"
  | "outline"
  | "ghost"
  | "danger";

export interface IconButtonProps
  extends ButtonHTMLAttributes<HTMLButtonElement> {
  icon: ReactNode;
  variant?: IconButtonVariant;
  size?: "sm" | "md" | "lg";
  loading?: boolean;
}

const variants: Record<IconButtonVariant, string> = {
  primary:
    "bg-blue-600 text-white hover:bg-blue-700 focus:ring-blue-500",

  secondary:
    "bg-slate-700 text-white hover:bg-slate-800 focus:ring-slate-500",

  outline:
    "border border-slate-300 bg-white text-slate-700 hover:bg-slate-50 focus:ring-slate-400",

  ghost:
    "bg-transparent text-slate-700 hover:bg-slate-100 focus:ring-slate-300",

  danger:
    "bg-red-600 text-white hover:bg-red-700 focus:ring-red-500",
};

const sizes = {
  sm: "h-8 w-8",
  md: "h-10 w-10",
  lg: "h-12 w-12",
};

const IconButton = forwardRef<HTMLButtonElement, IconButtonProps>(
  (
    {
      icon,
      variant = "ghost",
      size = "md",
      loading = false,
      className,
      disabled,
      ...props
    },
    ref
  ) => {
    return (
      <button
        ref={ref}
        disabled={disabled || loading}
        className={clsx(
          "inline-flex items-center justify-center rounded-md transition",
          "focus:outline-none focus:ring-2 focus:ring-offset-2",
          "disabled:cursor-not-allowed disabled:opacity-60",
          variants[variant],
          sizes[size],
          className
        )}
        {...props}
      >
        {loading ? (
          <span className="h-4 w-4 animate-spin rounded-full border-2 border-current border-t-transparent" />
        ) : (
          icon
        )}
      </button>
    );
  }
);

IconButton.displayName = "IconButton";

export default IconButton;
