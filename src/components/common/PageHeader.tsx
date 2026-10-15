import { ReactNode } from "react";
import clsx from "clsx";
import { Info, RefreshCw } from "lucide-react";
import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

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
  const client = useQueryClient();
  const [refreshing, setRefreshing] = useState(false);
  const refresh = async () => {
    setRefreshing(true);
    try { await client.refetchQueries({type: "active"}, {throwOnError: true}); }
    catch { toast.error("Unable to refresh data"); }
    finally { setRefreshing(false); }
  };
  return (
    <header
      className={clsx(
        "mb-1 flex flex-wrap items-center justify-between gap-1 border-b border-slate-200 pb-1",
        className
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2"><h1 className="text-base font-semibold tracking-tight text-slate-900">{title}</h1>{description && <button type="button" className="text-slate-400 hover:text-slate-700" title={description} aria-label={description}><Info size={14}/></button>}</div>



        {children}
      </div>

      <div className="flex flex-wrap items-center gap-1 print:hidden">{actions}<button type="button" disabled={refreshing} onClick={refresh} title="Refresh data" aria-label="Refresh data" className="grid h-8 w-8 place-items-center rounded border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-50"><RefreshCw size={15} className={refreshing ? "animate-spin" : ""}/></button></div>
    </header>
  );
}
