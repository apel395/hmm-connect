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
        "mb-6 flex flex-col gap-4 border-b border-slate-200 pb-5 md:flex-row md:items-center md:justify-between",
        className
      )}
    >
      <div className="min-w-0 flex-1">
        <h1 className="text-2xl font-bold tracking-tight text-slate-900">
          {title}
        </h1>

        {description && (
          <p className="mt-1 text-sm text-slate-500">
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

