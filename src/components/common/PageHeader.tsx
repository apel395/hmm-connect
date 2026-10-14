import { ReactNode } from "react";
import clsx from "clsx";

export interface PageHeaderProps {
  title: string;
  description?: string;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}

export default function PageHeader({
  title,
  description,
  actions,
  children,
  className,
}: PageHeaderProps) {
  return (
    <header
      className={clsx(
        "mb-2 flex flex-col gap-2 border-b border-slate-200 pb-2 sm:flex-row sm:items-center sm:justify-between",
        className
      )}
    >
      <div className="min-w-0 flex-1">
        <h1 className="text-lg font-semibold tracking-tight text-slate-900">
          {title}
        </h1>

        {description && (
          <p className="mt-0.5 text-xs leading-4 text-slate-500">
            {description}
          </p>
        )}

        {children}
      </div>

      {actions && (
        <div className="flex flex-wrap items-center gap-2">
          {actions}
        </div>
      )}
    </header>
  );
}
