import { ReactNode } from "react";
import clsx from "clsx";
import { Inbox } from "lucide-react";

export interface EmptyProps {
  title?: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export default function Empty({
  title = "No data found",
  description = "There is nothing to display at the moment.",
  icon,
  action,
  className,
}: EmptyProps) {
  return (
    <div
      className={clsx(
        "flex flex-col items-center justify-center rounded-lg border border-dashed border-slate-300 bg-slate-50 px-6 py-12 text-center",
        className
      )}
    >
      <div className="mb-4 text-slate-400">
        {icon ?? <Inbox className="h-12 w-12" />}
      </div>

      <h3 className="text-lg font-semibold text-slate-900">
        {title}
      </h3>

      <p className="mt-2 max-w-md text-sm text-slate-500">
        {description}
      </p>

      {action && (
        <div className="mt-6">
          {action}
        </div>
      )}
    </div>
  );
}
