import { useEffect, useState } from "react";
import {
  BarChart3, Boxes, Building2, ChevronDown, FileBarChart, Landmark,
  LayoutDashboard, Settings, ShoppingCart, X,
} from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import useAuthStore from "@/store/auth";
import { canAccess } from "@/lib/access";

interface Props { open?: boolean; onClose?: () => void }
interface Child { title: string; url?: string; roles?: string[]; disabled?: boolean; badge?: string }
interface Group { title: string; icon: typeof LayoutDashboard; url?: string; roles?: string[]; children?: Child[] }

const groups: Group[] = [
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
  { title: "Master Data", icon: Building2, children: [
    { title: "Items", url: "/products" },
    { title: "Suppliers", url: "/suppliers", roles: ["PURCHASING"] },
    { title: "Warehouses", url: "/warehouses" },
    { title: "Business Units", url: "/organization-dimensions?section=business-units", roles: ["ADMIN"] },
    { title: "Departments", url: "/organization-dimensions?section=departments", roles: ["ADMIN"] },
    { title: "Locations", url: "/organization-dimensions?section=locations", roles: ["ADMIN"] },
  ] },
  { title: "Purchasing", icon: ShoppingCart, children: [
    { title: "Purchase Requisition", url: "/purchase-requisitions" },
    { title: "Purchase Order", url: "/purchase-orders" },
    { title: "Receiving", url: "/receiving", roles: ["WAREHOUSE", "PURCHASING"] },
    { title: "Purchasing Documents", url: "/purchasing-documents", roles: ["PURCHASING", "FINANCE"] },
    { title: "Approval Inbox", disabled: true },
  ] },
  { title: "Inventory", icon: Boxes, children: [
    { title: "Stock", url: "/inventory", roles: ["WAREHOUSE"] },
    { title: "Stock Movement", url: "/inventory/movements", roles: ["WAREHOUSE"] },
    { title: "Stock Adjustment", disabled: true },
  ] },
  { title: "Finance", icon: Landmark, roles: ["FINANCE"], children: [
    { title: "Finance Dashboard", url: "/finance-dashboard" },
    { title: "Bank Reconciliation", url: "/bank-reconciliations" },
    { title: "Budgets", url: "/budgets", badge: "Worker" },
    { title: "Budget vs Actual", url: "/budget-vs-actual", badge: "Worker" },
    { title: "Fixed Assets", url: "/fixed-assets", badge: "Worker" },
    { title: "Asset Categories", url: "/asset-categories", badge: "Worker" },
    { title: "Depreciation Runs", url: "/depreciation-runs", badge: "Worker" },
    { title: "Chart of Accounts", url: "/chart-of-accounts" },
    { title: "Posting Rules", url: "/posting-rules" },
    { title: "Supplier Invoices", url: "/supplier-invoices" },
    { title: "Journal Entries", url: "/journal-entries" },
    { title: "Payments", url: "/payments" },
    { title: "General Ledger", url: "/general-ledger" },
    { title: "Cash Flow Dashboard", url: "/cash-flow" },
    { title: "Cash & Bank Accounts", url: "/cash-accounts" },
    { title: "Bank Transfers", url: "/bank-transfers" },
    { title: "Cash Flow Statement", url: "/cash-flow-statement" },
    { title: "Historical Import", url: "/historical-import", badge: "Worker" },
    { title: "Trial Balance", url: "/trial-balance", badge: "Worker" },
    { title: "Balance Sheet", url: "/balance-sheet" },
    { title: "Profit & Loss", url: "/profit-loss" },
  ] },
  { title: "Reports", icon: FileBarChart, children: [
    { title: "Purchasing Reports", url: "/audit", roles: ["ADMIN"] },
    { title: "Inventory Reports", disabled: true },
    { title: "Fixed Asset Register", url: "/reports/fixed-assets", roles:["FINANCE"], badge: "Worker" },
    { title: "Depreciation Report", url: "/reports/depreciation", roles:["FINANCE"], badge: "Worker" },
  ] },
  { title: "Administration", icon: Settings, roles: ["ADMIN"], children: [
    { title: "Users", url: "/users" },
    { title: "Roles", url: "/roles" },
    { title: "Permissions", url: "/settings" },
    { title: "Audit Logs", url: "/audit" },
    { title: "System Settings", url: "/settings" },
  ] },
];

export default function Sidebar({ open = false, onClose }: Props) {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const allowed = (roles?: string[]) => canAccess(user, roles);
  const activeParent = groups.find((group) => group.children?.some((child) => {
    if (!child.url) return false;
    const [path, query] = child.url.split("?");
    if (!location.pathname.startsWith(path)) return false;
    return !query || location.search === `?${query}`;
  }))?.title;
  const [expanded, setExpanded] = useState<string[]>(activeParent ? [activeParent] : []);
  useEffect(() => { if (activeParent) setExpanded((value) => value.includes(activeParent) ? value : [...value, activeParent]); }, [activeParent]);

  return <>
    {open && <button className="fixed inset-0 z-40 bg-black/40 lg:hidden" aria-label="Close navigation" onClick={onClose}/>}
    <aside className={`fixed inset-y-0 left-0 z-50 flex h-screen w-64 shrink-0 flex-col overflow-hidden bg-[#073F37] text-white transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="relative shrink-0 border-b border-white/10 px-4 py-3">
        <button className="absolute right-3 top-3 rounded-lg p-2 text-white/70 hover:bg-white/10 lg:hidden" aria-label="Close navigation" onClick={onClose}><X className="h-5 w-5"/></button>
        <div className="flex items-center gap-3 pr-9 lg:pr-0">
          <div className="grid h-12 w-14 shrink-0 place-items-center overflow-hidden rounded-lg bg-white p-1">
            <img src="/mutiara-merdeka-logo.svg" alt="Mutiara Merdeka" className="h-full w-full object-contain" />
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold tracking-wide" title="HMM-Connect">HMM-Connect</div>
            <div className="truncate text-[11px] text-emerald-100/70" title="Hotel Mutiara Merdeka">Hotel Mutiara Merdeka</div>
            <div className="text-[9px] tracking-[0.12em] text-[#D4AA1D]">★★★★</div>
          </div>
        </div>
      </div>
      <nav className="min-h-0 flex-1 space-y-0.5 overflow-y-auto overflow-x-hidden p-2.5">
        {groups.filter((group) => allowed(group.roles)).map((group) => {
          const Icon = group.icon;
          if (group.url) return <NavLink key={group.title} to={group.url} title={group.title} onClick={onClose} className={({isActive}) => `flex h-9 items-center gap-2.5 rounded-lg px-3 text-[13px] font-medium ${isActive ? "bg-[#0F6758] text-white" : "text-emerald-50/75 hover:bg-white/10"}`}><Icon className="h-4 w-4 shrink-0"/><span className="truncate">{group.title}</span></NavLink>;
          const children = group.children?.filter((child) => allowed(child.roles)) ?? [];
          const isExpanded = expanded.includes(group.title);
          return <div key={group.title}>
            <button type="button" title={group.title} aria-expanded={isExpanded} onClick={() => setExpanded((value) => value.includes(group.title) ? value.filter((item) => item !== group.title) : [...value, group.title])} className="flex h-9 w-full items-center gap-2.5 rounded-lg px-3 text-[13px] font-medium text-emerald-50/75 hover:bg-white/10"><Icon className="h-4 w-4 shrink-0"/><span className="min-w-0 flex-1 truncate text-left">{group.title}</span><ChevronDown className={`h-4 w-4 shrink-0 transition ${isExpanded ? "rotate-180" : ""}`}/></button>
            {isExpanded && <div className="ml-4 border-l border-white/10 pl-2">{children.map((child) => child.disabled ? <div key={child.title} className="flex h-8 items-center justify-between gap-2 px-2.5 text-xs text-emerald-100/35" title={`${child.title} — Coming Soon`}><span className="truncate">{child.title}</span><span className="text-[9px] uppercase">Soon</span></div> : <NavLink key={child.title} to={child.url!} title={child.title} onClick={onClose} className={({isActive}) => `flex h-8 items-center justify-between rounded-lg px-2.5 text-xs ${isActive ? "bg-[#0F6758] text-white" : "text-emerald-50/70 hover:bg-white/10 hover:text-white"}`}><span className="truncate">{child.title}</span>{child.badge && <span className="ml-2 text-[8px] uppercase tracking-wide text-[#D4AA1D]">{child.badge}</span>}</NavLink>)}</div>}
          </div>;
        })}
      </nav>
      <div className="shrink-0 border-t border-white/10 p-3 text-[11px] text-emerald-100/55"><div className="flex items-center gap-2"><BarChart3 className="h-4 w-4 text-[#D4AA1D]"/>Premium hotel operations</div></div>
    </aside>
  </>;
}
