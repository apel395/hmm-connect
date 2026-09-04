import { useEffect, useState } from "react";
import { BarChart3, Boxes, Building2, CheckSquare2, ChevronDown, FileBarChart, Landmark, LayoutDashboard, Settings, ShoppingCart, Store, X } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import useAuthStore from "@/store/auth";
import { canAccess } from "@/lib/access";

interface Props { open?: boolean; onClose?: () => void }
interface Child { title: string; url?: string; roles?: string[]; permission?: string; disabled?: boolean; badge?: string; exact?: boolean }
interface Group { title: string; icon: typeof LayoutDashboard; url?: string; roles?: string[]; permission?: string; children?: Child[] }

const INVENTORY_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "PURCHASING", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];
const POS_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];

const groups: Group[] = [
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard, permission: "dashboard.view" },
  { title: "Approval Center", url: "/approval-center", icon: CheckSquare2, permission: "approval.view", roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "DEPARTMENT", "GENERAL_MANAGER", "AUDITOR"] },
  { title: "Master Data", icon: Building2, roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"], children: [
    { title: "Items", url: "/products", permission: "products.view" },
    { title: "Suppliers", url: "/suppliers", permission: "suppliers.view", roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "Warehouses", url: "/warehouses", permission: "warehouse.view", roles: ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "Business Units", url: "/organization-dimensions?section=business-units", permission: "admin.settings.manage", roles: ["SYSTEM_ADMINISTRATOR"] },
    { title: "Departments", url: "/organization-dimensions?section=departments", permission: "admin.settings.manage", roles: ["SYSTEM_ADMINISTRATOR"] },
    { title: "Locations", url: "/organization-dimensions?section=locations", permission: "admin.settings.manage", roles: ["SYSTEM_ADMINISTRATOR"] },
  ] },
  { title: "Purchasing", icon: ShoppingCart, roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "DEPARTMENT", "GENERAL_MANAGER", "AUDITOR"], children: [
    { title: "Purchase Requisition", url: "/purchase-requisitions", permission: "pr.view", roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "DEPARTMENT", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "Market List", url: "/market-lists", permission: "market_list.view", roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "DEPARTMENT", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "Purchase Order", url: "/purchase-orders", permission: "po.view", roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "Receiving", url: "/receiving", permission: "receiving.view", roles: ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "PURCHASING", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  ] },
  { title: "Inventory", icon: Boxes, roles: [...INVENTORY_ROLES, "DEPARTMENT"], children: [
    { title: "Stock", url: "/inventory", exact: true, permission: "inventory.view", roles: INVENTORY_ROLES },
    { title: "Stock Movement", url: "/inventory/movements", permission: "inventory.view", roles: INVENTORY_ROLES },
    { title: "Store Request", url: "/store-requests", permission: "store_request.view", roles: ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "DEPARTMENT", "PURCHASING", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "Stock Opname", url: "/stock-opnames", permission: "stock_opname.view", roles: ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "Stock Adjustment", url: "/stock-adjustments", permission: "inventory.view", roles: INVENTORY_ROLES },
  ] },
  { title: "Point of Sales", icon: Store, roles: POS_ROLES, children: [
    { title: "Register", url: "/pos", exact: true, permission: "pos.view", roles: POS_ROLES },
    { title: "Sales", url: "/pos/sales", permission: "pos.view", roles: POS_ROLES },
  ] },
  { title: "Finance", icon: Landmark, roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"], children: [
    { title: "Finance Dashboard", url: "/finance-dashboard", permission: "finance.view" },
    { title: "Accounts Payable", url: "/accounts-payable", permission: "ap.view" },
    { title: "Accounts Receivable", url: "/accounts-receivable", permission: "finance.view" },
    { title: "Cash & Bank", url: "/cash-bank", permission: "finance.view" },
    { title: "Journal", url: "/journal", permission: "journal.view" },
    { title: "Opening Balances", url: "/opening-balances", permission: "journal.manage" },
    { title: "Reconciliation", url: "/financial-reconciliation", permission: "finance.view" },
    { title: "Fixed Assets", url: "/fixed-assets", permission: "finance.view" },
    { title: "Fiscal COA", url: "/fiscal-coa", permission: "fiscal.view", roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  { title: "Fiscal Reconciliation", url: "/fiscal-reconciliation", permission: "fiscal.view", roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  { title: "SPT Tahunan 1771", url: "/spt-1771", permission: "fiscal.view", roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  ] },
  { title: "Reports", icon: FileBarChart, children: [
    { title: "Purchasing Reports", url: "/reports/purchasing", permission: "reports.purchasing", roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "Inventory Reports", url: "/reports/inventory", permission: "inventory.view", roles: INVENTORY_ROLES },
    { title: "Cash Flow Statement", url: "/cash-flow-statement", permission: "reports.view", roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR", "VIEWER"] },
    { title: "Balance Sheet", url: "/balance-sheet", permission: "reports.view", roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR", "VIEWER"] },
    { title: "Profit & Loss", url: "/profit-loss", permission: "reports.view", roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR", "VIEWER"] },
  ] },
  { title: "Administration", icon: Settings, roles: ["SYSTEM_ADMINISTRATOR"], children: [
    { title: "Users", url: "/users", permission: "admin.users.manage" },
    { title: "Roles", url: "/roles", permission: "admin.roles.manage" },
    { title: "Finance Setup", url: "/finance-setup", permission: "finance.manage" },
    { title: "System Settings", url: "/settings", permission: "admin.settings.manage" },
  ] },
];

export default function Sidebar({ open = false, onClose }: Props) {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const allowed = (roles?: string[], permission?: string) => canAccess(user, roles, permission);
  const childIsActive = (child: Child) => {
    if (!child.url) return false;
    const [path, query] = child.url.split("?");
    const pathMatches = child.exact
      ? location.pathname === path
      : location.pathname === path || location.pathname.startsWith(`${path}/`);
    if (!pathMatches) return false;
    return query ? location.search === `?${query}` : true;
  };
  const activeParent = groups.find((group) => group.children?.some((child) => childIsActive(child)))?.title;
  const [expanded, setExpanded] = useState<string[]>(activeParent ? [activeParent] : []);
  useEffect(() => { if (activeParent) setExpanded((value) => value.includes(activeParent) ? value : [...value, activeParent]); }, [activeParent]);

  return <>
    {open && <button className="fixed inset-0 z-40 bg-black/40 lg:hidden" aria-label="Close navigation" onClick={onClose}/>}
    <aside className={`fixed inset-y-0 left-0 z-50 flex h-screen w-64 shrink-0 flex-col overflow-hidden bg-[#073F37] text-white transition-transform lg:static lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="relative shrink-0 border-b border-white/10 px-4 py-3"><button className="absolute right-3 top-3 rounded-lg p-2 text-white/70 hover:bg-white/10 lg:hidden" aria-label="Close navigation" onClick={onClose}><X className="h-5 w-5"/></button><div className="flex items-center gap-3 pr-9 lg:pr-0"><div className="grid h-12 w-14 shrink-0 place-items-center overflow-hidden rounded-lg bg-white p-1"><img src="/mutiara-merdeka-logo.svg" alt="Mutiara Merdeka" className="h-full w-full object-contain" /></div><div className="min-w-0"><div className="truncate text-sm font-semibold tracking-wide">HMM-Connect</div><div className="truncate text-[11px] text-emerald-100/70">Hotel Mutiara Merdeka</div><div className="text-[9px] tracking-[0.12em] text-[#D4AA1D]">★★★★</div></div></div></div>
      <nav className="min-h-0 flex-1 space-y-0.5 overflow-y-auto overflow-x-hidden p-2.5">{groups.filter((group) => group.url ? allowed(group.roles, group.permission) : (group.children?.some((child) => allowed(child.roles, child.permission)) ?? false)).map((group) => { const Icon = group.icon; if (group.url) return <NavLink key={group.title} to={group.url} onClick={onClose} className={({isActive}) => `flex h-9 items-center gap-2.5 rounded-lg px-3 text-[13px] font-medium ${isActive ? "bg-[#0F6758] text-white" : "text-emerald-50/75 hover:bg-white/10"}`}><Icon className="h-4 w-4 shrink-0"/><span className="truncate">{group.title}</span></NavLink>; const children = group.children?.filter((child) => allowed(child.roles, child.permission)) ?? []; const isExpanded = expanded.includes(group.title); return <div key={group.title}><button type="button" aria-expanded={isExpanded} onClick={() => setExpanded((value) => value.includes(group.title) ? value.filter((item) => item !== group.title) : [...value, group.title])} className="flex h-9 w-full items-center gap-2.5 rounded-lg px-3 text-[13px] font-medium text-emerald-50/75 hover:bg-white/10"><Icon className="h-4 w-4 shrink-0"/><span className="min-w-0 flex-1 truncate text-left">{group.title}</span><ChevronDown className={`h-4 w-4 shrink-0 transition ${isExpanded ? "rotate-180" : ""}`}/></button>{isExpanded && <div className="ml-4 border-l border-white/10 pl-2">{children.map((child) => child.disabled ? <div key={child.title} className="flex h-8 items-center justify-between gap-2 px-2.5 text-xs text-emerald-100/35"><span className="truncate">{child.title}</span><span className="text-[9px] uppercase">Soon</span></div> : <NavLink key={child.title} to={child.url!} onClick={onClose} className={() => `flex h-8 items-center justify-between rounded-lg px-2.5 text-xs ${childIsActive(child) ? "bg-[#0F6758] text-white" : "text-emerald-50/70 hover:bg-white/10 hover:text-white"}`} title={child.title}><span className="truncate">{child.title}</span>{child.badge && <span className="ml-2 text-[8px] uppercase tracking-wide text-[#D4AA1D]">{child.badge}</span>}</NavLink>)}</div>}</div>; })}</nav>
      <div className="shrink-0 border-t border-white/10 p-3 text-[11px] text-emerald-100/55"><div className="flex items-center gap-2"><BarChart3 className="h-4 w-4 text-[#D4AA1D]"/>Premium hotel operations</div></div>
    </aside>
  </>;
}
