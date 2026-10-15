import { useEffect, useId, useState } from "react";
import { createPortal } from "react-dom";
import { BarChart3, Crown, Boxes, Building2, CheckSquare2, ChevronDown, FileBarChart, Landmark, LayoutDashboard, Scale, Settings, ShoppingCart, Store, X, PanelLeftClose } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import useAuthStore from "@/store/auth";
import { canAccess } from "@/lib/access";

interface Props { open?: boolean; onClose?: () => void; collapsed: boolean; onToggle: () => void }
interface Child { title: string; url?: string; roles?: string[]; permission?: string; disabled?: boolean; badge?: string; exact?: boolean }
interface Group { title: string; icon: typeof LayoutDashboard; url?: string; roles?: string[]; permission?: string; permissions?: string[]; children?: Child[] }

const INVENTORY_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "PURCHASING", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];
const POS_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];

const groups: Group[] = [
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard, permission: "dashboard.view" },
  { title: "Executive View", url: "/executive-view", icon: Crown, permissions: ["reports.view", "finance.view"] },
  { title: "Approval Center", url: "/approval-center", icon: CheckSquare2, permission: "approval.view", roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "DEPARTMENT", "GENERAL_MANAGER", "AUDITOR"] },
  { title: "Master Data", icon: Building2, roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"], children: [
    { title: "Catering Items", url: "/products", permission: "products.view" },
    { title: "Hotel Items", url: "/hotel-items", permission: "products.view" },
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
  { title: "Finance", icon: Landmark, roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "AP", "GENERAL_MANAGER", "AUDITOR"], children: [
    { title: "Statistics", url: "/statistics", permission: "finance.view" },
    { title: "Budget Input", url: "/budgets", permission: "finance.view" },
    { title: "Finance Dashboard", url: "/finance-dashboard", permission: "finance.view" },
    { title: "Accounts Payable", url: "/accounts-payable", permission: "ap.view", roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "AP", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "Accounts Receivable", url: "/accounts-receivable", permission: "finance.view" },
    { title: "General Cashier", url: "/cash-bank/cashier", permission: "finance.view" },
    { title: "Petty Cash", url: "/cash-bank/petty-cash", permission: "finance.view" },
    { title: "Cash & Bank", url: "/cash-bank", permission: "finance.view" },
    { title: "Journal", url: "/journal", permission: "journal.view" },
    { title: "Accounting Periods", url: "/finance-setup/accounting-periods", permission: "finance.manage" },
    { title: "Reconciliation", url: "/financial-reconciliation", permission: "finance.view" },
    { title: "Fixed Assets", url: "/fixed-assets", permission: "finance.view" },
  ] },
  { title: "Fiscal", icon: Scale, roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"], children: [
    { title: "Fiscal COA", url: "/finance/fiscal/coa", exact: true, permission: "fiscal.view", roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "Fiscal Reconciliation", url: "/finance/fiscal/reconciliation", permission: "fiscal.view", roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "Lampiran 1D", url: "/finance/fiscal/lampiran-1d", permission: "fiscal.view", roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
    { title: "SPT Tahunan 1771", url: "/finance/fiscal/spt-1771", permission: "fiscal.view", roles: ["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
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
    { title: "Report Setup", url: "/finance-setup/reports", permission: "finance.manage" },
    { title: "Finance Setup", url: "/finance-setup", permission: "finance.manage" },
    { title: "System Settings", url: "/settings", permission: "admin.settings.manage" },
  ] },
];

export default function Sidebar({ open = false, onClose, collapsed, onToggle }: Props) {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const [flyout, setFlyout] = useState<string | null>(null);
  const [tooltip, setTooltip] = useState<{ title: string; top: number } | null>(null);
  const tooltipId = useId();
  const showTooltip = (title: string, target: HTMLElement) => {
    const bounds = target.getBoundingClientRect();
    setTooltip({ title, top: Math.max(20, Math.min(window.innerHeight - 20, bounds.top + bounds.height / 2)) });
  };
  const allowed = (roles?: string[], permission?: string) => canAccess(user, roles, permission);
  const childIsActive = (child: Child) => {
    if (!child.url) return false;
    const [path, query] = child.url.split("?");
    const pathMatches = child.exact
      ? location.pathname === path
      : location.pathname === path || location.pathname.startsWith(`${path}/`);
    return pathMatches && (!query || location.search === `?${query}`);
  };
  const visibleGroups = groups.filter(group => group.url
    ? (group.permissions ? group.permissions.some(permission => allowed(group.roles,permission)) : allowed(group.roles, group.permission))
    : group.children?.some(child => allowed(child.roles, child.permission)));
  const activeParent = visibleGroups.find(group => group.children?.some(childIsActive))?.title;
  const [expanded, setExpanded] = useState<string[]>(activeParent ? [activeParent] : []);
  useEffect(() => {
    if (activeParent) setExpanded(value => value.includes(activeParent) ? value : [...value, activeParent]);
  }, [activeParent]);
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") { setTooltip(null); setFlyout(null); onClose?.(); }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);
  useEffect(() => {
    const hideTooltip = () => setTooltip(null);
    window.addEventListener("resize", hideTooltip);
    window.addEventListener("scroll", hideTooltip, true);
    return () => {
      window.removeEventListener("resize", hideTooltip);
      window.removeEventListener("scroll", hideTooltip, true);
    };
  }, []);
  const closeNavigation = () => { setTooltip(null); setFlyout(null); onClose?.(); };
  const toggleSidebar = () => { setTooltip(null); setFlyout(null); onToggle(); };
  const selectedGroup = visibleGroups.find(group => group.title === flyout);
  const renderChildren = (group: Group) => (group.children ?? [])
    .filter(child => allowed(child.roles, child.permission))
    .map(child => child.disabled
      ? <div key={child.title} className="flex h-8 items-center justify-between gap-2 px-2.5 text-xs text-emerald-100/35">
          <span className="truncate">{child.title}</span><span className="text-[9px] uppercase">Soon</span>
        </div>
      : <NavLink key={child.title} to={child.url!} onClick={closeNavigation}
          className={`flex h-8 items-center justify-between rounded-lg px-2.5 text-xs ${childIsActive(child) ? "bg-[#0F6758] text-white" : "text-emerald-50/70 hover:bg-white/10 hover:text-white"}`}
          title={child.title}>
          <span className="truncate">{child.title}</span>
          {child.badge && <span className="ml-2 text-[8px] uppercase tracking-wide text-[#D4AA1D]">{child.badge}</span>}
        </NavLink>);

  return <>
    {collapsed && <aside aria-label="Module navigation" className="relative z-50 hidden h-screen w-16 shrink-0 flex-col border-r border-white/10 bg-[#103E36] text-white lg:flex">
      <div className="flex h-12 shrink-0 items-center justify-center border-b border-white/10">
        <button type="button" onClick={toggleSidebar} aria-label="Expand navigation"
          aria-describedby={tooltip?.title === "Expand navigation" ? tooltipId : undefined}
          onMouseEnter={event => showTooltip("Expand navigation", event.currentTarget)}
          onMouseLeave={() => setTooltip(null)} onFocus={event => showTooltip("Expand navigation", event.currentTarget)}
          onBlur={() => setTooltip(null)} className="rounded-lg p-2 text-emerald-50/80 hover:bg-white/10">
          <span className="text-[11px] font-bold tracking-tight">MMH</span>
        </button>
      </div>
      <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">
        {visibleGroups.map(group => {
          const Icon = group.icon;
          const active = group.title === activeParent || group.title === flyout;
          const iconClass = `flex h-10 w-full items-center justify-center rounded-lg ${active ? "bg-[#0F6758] text-white" : "text-emerald-50/75 hover:bg-white/10"}`;
          return group.url
            ? <NavLink key={group.title} to={group.url} onClick={closeNavigation} aria-label={group.title}
                aria-describedby={tooltip?.title === group.title ? tooltipId : undefined}
                onMouseEnter={event => showTooltip(group.title, event.currentTarget)}
                onMouseLeave={() => setTooltip(null)} onFocus={event => showTooltip(group.title, event.currentTarget)}
                onBlur={() => setTooltip(null)}
                className={({ isActive }) => `${iconClass} ${isActive ? "bg-[#0F6758] text-white" : ""}`}>
                <Icon className="h-5 w-5"/>
              </NavLink>
            : <button key={group.title} type="button" aria-label={group.title}
                aria-describedby={tooltip?.title === group.title ? tooltipId : undefined}
                onMouseEnter={event => showTooltip(group.title, event.currentTarget)}
                onMouseLeave={() => setTooltip(null)} onFocus={event => showTooltip(group.title, event.currentTarget)}
                onBlur={() => setTooltip(null)}
                aria-expanded={flyout === group.title} aria-controls="sidebar-module-flyout"
                onClick={() => { setTooltip(null); setFlyout(value => value === group.title ? null : group.title); }} className={iconClass}>
                <Icon className="h-5 w-5"/>
              </button>;
        })}
      </nav>
    </aside>}
    {collapsed && tooltip && createPortal(
      <div id={tooltipId} role="tooltip"
        className="pointer-events-none fixed z-[100] hidden max-w-64 -translate-y-1/2 whitespace-nowrap rounded-md bg-[#103E36] px-3 py-2 text-xs font-medium text-white shadow-lg lg:block"
        style={{ left: "4.5rem", top: tooltip.top }}>
        <span aria-hidden="true" className="absolute -left-1 top-1/2 h-2 w-2 -translate-y-1/2 rotate-45 bg-[#103E36]" />
        {tooltip.title}
      </div>, document.body)}
    {collapsed && selectedGroup && <>
      <button type="button" className="fixed inset-0 z-40 hidden bg-black/10 lg:block" aria-label="Close module submenu" onClick={() => setFlyout(null)}/>
      <section id="sidebar-module-flyout" aria-label={selectedGroup.title} className="fixed bottom-0 left-16 top-0 z-50 hidden w-64 flex-col border-l border-white/10 bg-[#103E36] text-white shadow-xl lg:flex">
        <div className="flex h-12 shrink-0 items-center justify-between border-b border-white/10 px-3">
          <span className="text-sm font-semibold">{selectedGroup.title}</span>
          <button type="button" aria-label="Close module submenu" onClick={() => setFlyout(null)} className="rounded p-2 hover:bg-white/10"><X className="h-4 w-4"/></button>
        </div>
        <nav className="min-h-0 flex-1 space-y-1 overflow-y-auto p-2">{renderChildren(selectedGroup)}</nav>
      </section>
    </>}
    {open && <button type="button" className="fixed inset-0 z-40 bg-black/40 lg:hidden" aria-label="Close navigation" onClick={onClose}/>}
    <aside aria-label="Full navigation" className={`fixed inset-y-0 left-0 z-50 h-screen w-64 shrink-0 flex-col overflow-hidden bg-[#103E36] text-white lg:static ${open ? "flex" : "hidden"} ${collapsed ? "lg:hidden" : "lg:flex"}`}>
      <div className="relative shrink-0 border-b border-white/10 px-3 py-3">
        <button type="button" className="absolute right-2 top-3 rounded-lg p-2 text-white/70 hover:bg-white/10 lg:hidden" aria-label="Close navigation" onClick={onClose}><X className="h-5 w-5"/></button>
        <button type="button" className="absolute right-2 top-3 hidden rounded-lg p-2 text-white/70 hover:bg-white/10 lg:block" aria-label="Collapse navigation" title="Collapse navigation" onClick={toggleSidebar}><PanelLeftClose className="h-5 w-5"/></button>
        <div className="flex items-center gap-2 pr-9">
          <div className="grid h-10 w-12 shrink-0 place-items-center rounded-lg bg-white p-1"><img src="/mutiara-merdeka-logo.svg" alt="Mutiara Merdeka" className="h-full w-full object-contain"/></div>
          <div className="min-w-0"><div className="truncate text-sm font-semibold">MMH-Connect</div><div className="truncate text-[10px] text-emerald-100/70">Hotel Mutiara Merdeka</div></div>
        </div>
      </div>
      <nav className="min-h-0 flex-1 space-y-0.5 overflow-y-auto overflow-x-hidden p-2.5">
        {visibleGroups.map(group => {
          const Icon = group.icon;
          if (group.url) return <NavLink key={group.title} to={group.url} onClick={closeNavigation}
            className={({ isActive }) => `flex h-9 items-center gap-2.5 rounded-lg px-3 text-[13px] font-medium ${isActive ? "bg-[#0F6758] text-white" : "text-emerald-50/75 hover:bg-white/10"}`}>
            <Icon className="h-4 w-4 shrink-0"/><span className="truncate">{group.title}</span>
          </NavLink>;
          const isExpanded = expanded.includes(group.title);
          return <div key={group.title}>
            <button type="button" aria-expanded={isExpanded}
              onClick={() => setExpanded(value => value.includes(group.title) ? value.filter(item => item !== group.title) : [...value, group.title])}
              className="flex h-9 w-full items-center gap-2.5 rounded-lg px-3 text-[13px] font-medium text-emerald-50/75 hover:bg-white/10">
              <Icon className="h-4 w-4 shrink-0"/><span className="min-w-0 flex-1 truncate text-left">{group.title}</span><ChevronDown className={`h-4 w-4 shrink-0 transition ${isExpanded ? "rotate-180" : ""}`}/>
            </button>
            {isExpanded && <div className="ml-4 border-l border-white/10 pl-2">{renderChildren(group)}</div>}
          </div>;
        })}
      </nav>
      <div className="shrink-0 border-t border-white/10 p-3 text-[11px] text-emerald-100/55"><div className="flex items-center gap-2"><BarChart3 className="h-4 w-4 text-[#D4AA1D]"/>MMH · Operations</div></div>
    </aside>
  </>;
}
