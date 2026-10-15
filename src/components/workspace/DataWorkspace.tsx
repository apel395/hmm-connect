import { useState, type ReactNode } from "react";
import { SlidersHorizontal } from "lucide-react";
import { DataWorkspaceContext, type WorkspaceArea } from "./dataWorkspaceContext";

/** Opt-in screen layout. Print and accounting data remain owned by each module. */
export default function DataWorkspace({ area, children, className = "" }: {
  area: WorkspaceArea;
  children: ReactNode;
  className?: string;
}) {
  const [dense, setDense] = useState(() => {
    try { return localStorage.getItem("mmh-workspace-density") === "dense"; }
    catch { return false; }
  });
  const toggleDensity = () => setDense(current => {
    const next = !current;
    try { localStorage.setItem("mmh-workspace-density", next ? "dense" : "compact"); }
    catch { /* Storage can be unavailable in a private browser. */ }
    return next;
  });
  return <DataWorkspaceContext.Provider value={{ area, dense, toggleDensity }}>
    <section className={`data-workspace ${className}`} data-density={dense ? "dense" : "compact"} aria-label={`${area} workspace`}>
      {children}
    </section>
  </DataWorkspaceContext.Provider>;
}

/** Secondary controls take no table space until requested; values stay mounted. */
export function WorkspaceFilters({ children, label = "Filters", context }: {
  children: ReactNode;
  label?: string;
  context?: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return <div className="workspace-filter-panel print:hidden">
    <div className="workspace-filter-heading">
      <span className="min-w-0 truncate text-xs text-slate-500">{context}</span>
      <button type="button" className="workspace-tool" title={label} aria-label={label} aria-expanded={open} onClick={() => setOpen(!open)}><SlidersHorizontal size={16}/></button>
    </div>
    <div hidden={!open} className="workspace-filter-fields">{children}</div>
  </div>;
}
