import { NavLink, useLocation } from "react-router-dom";

export interface WorkspaceTab {
  label: string;
  to: string;
  exact?: boolean;
}

interface Props {
  title: string;
  description: string;
  tabs: WorkspaceTab[];
  ariaLabel?: string;
}

export default function ModuleWorkspaceHeader({ title, description, tabs, ariaLabel }: Props) {
  const location = useLocation();

  return (
    <div className="border-b border-slate-200 bg-white">
      <div className="pb-3">
        <h1 className="text-2xl font-semibold tracking-tight text-slate-900">{title}</h1>
        <p className="mt-1 text-sm text-slate-500">{description}</p>
      </div>
      <nav className="flex min-w-max gap-7 overflow-x-auto" aria-label={ariaLabel ?? `${title} workspace`}>
        {tabs.map((tab) => {
          const active = tab.exact ? location.pathname === tab.to : location.pathname.startsWith(tab.to);
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={`relative whitespace-nowrap px-1 pb-3 pt-1 text-sm font-medium transition-colors ${active ? "text-[#086B5A]" : "text-slate-500 hover:text-slate-900"}`}
            >
              {tab.label}
              {active && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-[#086B5A]" />}
            </NavLink>
          );
        })}
      </nav>
    </div>
  );
}
