import UsageGuide from "./UsageGuide";
import { DataWorkspaceContext } from "@/components/workspace/dataWorkspaceContext";
import { useContext, ReactNode } from "react";
import clsx from "clsx";
import { Info, RefreshCw, Building2, Boxes, BookOpen, ChartNoAxesCombined, Rows3 } from "lucide-react";
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
  const workspace = useContext(DataWorkspaceContext);
  const ModuleIcon = workspace ? ({ "Master data": Building2, Inventory: Boxes, Accounting: BookOpen, Reports: ChartNoAxesCombined }[workspace.area]) : null;
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
        "workspace-page-header mb-1 flex flex-wrap items-center justify-between gap-1 border-b border-slate-200 pb-1",
        className
      )}
    >
      <div className="workspace-page-identity min-w-0 flex-1">
        {ModuleIcon && <span className="workspace-module-icon print:hidden"><ModuleIcon size={20}/></span>}
        <div className="min-w-0">{workspace && <div className="workspace-eyebrow print:hidden">{workspace.area}</div>}
        <div className="flex items-center gap-2"><h1 className="text-[17px] font-semibold tracking-tight text-slate-900">{title}</h1>{description && <button type="button" className="text-slate-400 hover:text-slate-700" title={description} aria-label={description}><Info size={14}/></button>}</div>



        {children}
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-1 print:hidden">{actions}<UsageGuide title={title}/>{workspace && <button type="button" className="workspace-tool" title={workspace.dense ? "Use compact rows" : "Use extra compact rows"} aria-label="Extra compact rows" aria-pressed={workspace.dense} onClick={workspace.toggleDensity}><Rows3 size={16}/></button>}<button type="button" disabled={refreshing} onClick={refresh} title="Refresh data" aria-label="Refresh data" className="grid h-8 w-8 place-items-center rounded border border-slate-200 bg-white text-slate-600 hover:bg-slate-50 disabled:opacity-50"><RefreshCw size={15} className={refreshing ? "animate-spin" : ""}/></button></div>
    </header>
  );
}
