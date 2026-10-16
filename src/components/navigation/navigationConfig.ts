import { BarChart3, Crown, Boxes, Building2, CheckSquare2, FileBarChart, Landmark, LayoutDashboard, Scale, Settings, ShoppingCart, Store, Package, Hotel, Truck, Warehouse, Network, Users, MapPin, ClipboardList, ListChecks, FileText, PackageCheck, ArrowLeftRight, ClipboardCheck, SlidersHorizontal, Calculator, Wallet, Receipt, BookOpen, CalendarDays, GitCompareArrows, Armchair, ChartNoAxesCombined, ShieldCheck, type LucideIcon } from "lucide-react";
import { canAccess } from "@/lib/access";


export interface NavigationChild { title: string; url?: string; roles?: string[]; permission?: string; disabled?: boolean; badge?: string; exact?: boolean }
export interface NavigationGroup { title: string; icon: LucideIcon; url?: string; roles?: string[]; permission?: string; permissions?: string[]; children?: NavigationChild[] }
const INVENTORY_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "PURCHASING", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];
const POS_ROLES = ["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"];

export const navigationGroups: NavigationGroup[] = [
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard, permission: "dashboard.view" },
  { title: "Executive View", url: "/executive-view", icon: Crown, permissions: ["reports.view", "finance.view"] },
  { title: "Approval Center", url: "/approval-center", icon: CheckSquare2, permission: "approval.view", roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "DEPARTMENT", "GENERAL_MANAGER", "AUDITOR"] },
  { title: "Master Data", icon: Building2, roles: ["SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"], children: [
    { title: "Catering Buy Items", url: "/products", permission: "products.view" },
    { title: "Hotel Buy Items", url: "/hotel-items", permission: "products.view" },
    { title: "Catering Sell Items", url: "/sell-items", permission: "products.view" },
    { title: "Hotel Sell Items", url: "/hotel-sell-items", permission: "products.view" },
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


type NavigationUser = Parameters<typeof canAccess>[0];
export function visibleNavigation(user: NavigationUser): NavigationGroup[] {
  return navigationGroups.flatMap(group => {
    if (group.url) return (group.permissions ? group.permissions.some(permission => canAccess(user, group.roles, permission)) : canAccess(user, group.roles, group.permission)) ? [group] : [];
    const children = group.children?.filter(child => canAccess(user, child.roles, child.permission));
    return children?.length ? [{ ...group, children }] : [];
  });
}

const aliases: Record<string, string[]> = {
  "/journal": ["/journal-entries", "/general-ledger", "/trial-balance"],
  "/accounts-payable": ["/supplier-invoices", "/payments", "/supplier-adjustments"],
  "/accounts-receivable": ["/customer-invoices", "/customer-payments"],
  "/cash-bank": ["/cash-accounts", "/bank-transfers", "/bank-reconciliations", "/cash-flow"],
  "/finance-setup": ["/chart-of-accounts", "/opening-balances", "/posting-rules"],
  "/finance-setup/accounting-periods": ["/fiscal-periods"],
};
export function navigationMatches(item: NavigationChild, pathname: string, search: string): boolean {
  if (!item.url) return false;
  const [path, query] = item.url.split("?");
  const paths = [path, ...(aliases[path] ?? [])];
  const matches = paths.some(candidate => pathname === candidate || (!item.exact && pathname.startsWith(`${candidate}/`)));
  const actual = new URLSearchParams(search);
  return matches && (!query || [...new URLSearchParams(query)].every(([key, value]) => actual.get(key) === value));
}
export function activeNavigation(groups: NavigationGroup[], pathname: string, search: string) {
  // Prefer specific children (cashier, accounting periods) over their parent URL.
  const matches = groups.flatMap(group => (group.url ? [group] : group.children ?? []).filter(child => navigationMatches(child, pathname, search)).map(child => ({ group, child })));
  return matches.sort((a,b) => (b.child.url?.length ?? 0) - (a.child.url?.length ?? 0))[0];
}

const childIcons: Record<string, LucideIcon> = {
  "/sell-items": Package, "/hotel-sell-items": Hotel, "/products": Package, "/hotel-items": Hotel, "/suppliers": Truck, "/warehouses": Warehouse,
  "/organization-dimensions?section=business-units": Network, "/organization-dimensions?section=departments": Users, "/organization-dimensions?section=locations": MapPin,
  "/purchase-requisitions": ClipboardList, "/market-lists": ListChecks, "/purchase-orders": FileText, "/receiving": PackageCheck,
  "/inventory": Boxes, "/inventory/movements": ArrowLeftRight, "/store-requests": ClipboardList, "/stock-opnames": ClipboardCheck, "/stock-adjustments": SlidersHorizontal,
  "/statistics": BarChart3, "/budgets": Calculator, "/finance-dashboard": ChartNoAxesCombined, "/accounts-payable": Wallet, "/accounts-receivable": Receipt,
  "/cash-bank/cashier": Wallet, "/cash-bank/petty-cash": Wallet, "/cash-bank": Landmark, "/journal": BookOpen, "/finance-setup/accounting-periods": CalendarDays,
  "/financial-reconciliation": GitCompareArrows, "/fixed-assets": Armchair, "/users": Users, "/roles": ShieldCheck,
};
export const navigationIcon = (item: NavigationChild): LucideIcon => childIcons[item.url ?? ""] ?? FileBarChart;
