import { NavLink, useLocation } from "react-router-dom";

const tabs = [
  { label: "Receivables Summary", to: "/accounts-receivable", exact: true },
  { label: "Receivables Detail", to: "/accounts-receivable/detail" },
  { label: "AR Aging", to: "/accounts-receivable/aging" },
];

export default function ARWorkspaceHeader() {
  const location = useLocation();

  return (
    <nav className="flex min-w-max gap-6 overflow-x-auto border-b border-slate-200" aria-label="Accounts Receivable workspace">
      {tabs.map((tab) => {
        const active = tab.exact ? location.pathname === tab.to : location.pathname.startsWith(tab.to);
        return (
          <NavLink
            key={tab.to}
            to={tab.to}
            className={`relative whitespace-nowrap px-1 pb-2 pt-1 text-[13px] font-medium transition-colors ${
              active ? "text-[#086B5A]" : "text-slate-500 hover:text-slate-900"
            }`}
          >
            {tab.label}
            {active && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-[#086B5A]" />}
          </NavLink>
        );
      })}
    </nav>
  );
}
