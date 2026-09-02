const exactTitles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/approval-center": "Approval Center",
  "/approval-configuration": "Approval Configuration",
  "/finance-dashboard": "Finance Dashboard",
  "/purchase-requisitions": "Purchase Requisitions",
  "/market-lists": "Market List",
  "/purchase-orders": "Purchase Orders",
  "/receiving": "Receiving",
  "/purchasing-documents": "Purchasing Documents",
  "/inventory": "Inventory",
  "/inventory/movements": "Stock Movement",
  "/reports/inventory": "Inventory Reports",
  "/stock-adjustments": "Stock Adjustment",
  "/pos": "Point of Sales",
  "/pos/sales": "POS Sales",
  "/reports/purchasing": "Purchasing Reports",
  "/products": "Items",
  "/suppliers": "Suppliers",
  "/warehouses": "Warehouses",
  "/accounts-payable": "AP Overview",
  "/accounts-payable/aging": "AP Aging",
  "/accounts-payable/invoices": "Supplier Invoices",
  "/accounts-payable/payments": "Payments",
  "/accounts-payable/adjustments": "Credit / Debit Notes",
  "/supplier-invoices": "Supplier Invoices",
  "/payments": "Payments",
  "/supplier-adjustments": "Credit / Debit Notes",
  "/journal": "Journal",
  "/journal/general-ledger": "General Ledger",
  "/journal/trial-balance": "Trial Balance",
  "/journal-entries": "Journal",
  "/cash-bank": "Cash & Bank",
  "/cash-bank/accounts": "Bank Accounts",
  "/cash-bank/transfers": "Bank Transfers",
  "/cash-bank/reconciliation": "Bank Reconciliation",
  "/cash-bank/cash-flow": "Cash Flow",
  "/cash-accounts": "Cash & Bank Accounts",
  "/bank-transfers": "Bank Transfers",
  "/bank-reconciliations": "Bank Reconciliation",
  "/finance-setup": "Finance Setup",
  "/finance-setup/posting-rules": "Direct COA Setup",
  "/finance-setup/fiscal-periods": "Fiscal Periods",
  "/chart-of-accounts": "Chart of Accounts",
  "/posting-rules": "Direct COA Setup",
  "/fiscal-periods": "Fiscal Periods",
  "/fixed-assets": "Fixed Assets",
  "/fixed-assets/categories": "Asset Categories",
  "/fixed-assets/depreciation": "Depreciation",
  "/fixed-assets/amortization": "Amortization",
  "/fixed-assets/reports": "Fixed Asset Reports",
  "/general-ledger": "General Ledger",
  "/cash-flow": "Cash Flow Dashboard",
  "/cash-flow-statement": "Cash Flow Statement",
  "/trial-balance": "Trial Balance",
  "/balance-sheet": "Balance Sheet",
  "/profit-loss": "Profit & Loss",
  "/users": "Users",
  "/roles": "Roles",
  "/settings": "System Settings",
  "/organization-dimensions": "Organization",
  "/notifications": "Notifications",
  "/profile": "Profile",
};

const detailRules: Array<[RegExp, (match: RegExpMatchArray) => string]> = [
  [/^\/purchase-requisitions\/(\d+)$/, (m) => `PR #${m[1]}`],
  [/^\/market-lists\/(\d+)$/, (m) => `Market List #${m[1]}`],
  [/^\/purchase-orders\/(\d+)$/, (m) => `PO #${m[1]}`],
  [/^\/receiving\/(\d+)$/, (m) => `Receiving #${m[1]}`],
  [/^\/supplier-invoices\/(\d+)$/, (m) => `Invoice #${m[1]}`],
  [/^\/payments\/(\d+)$/, (m) => `Payment #${m[1]}`],
  [/^\/journal-entries\/(\d+)$/, (m) => `Journal #${m[1]}`],
  [/^\/cash-accounts\/(\d+)$/, (m) => `Cash Account #${m[1]}`],
  [/^\/bank-transfers\/(\d+)$/, (m) => `Bank Transfer #${m[1]}`],
  [/^\/bank-reconciliations\/(\d+)$/, (m) => `Reconciliation #${m[1]}`],
  [/^\/fixed-assets\/(\d+)$/, (m) => `Asset #${m[1]}`],
];

export function workspaceTitle(pathname: string, search = ""): string {
  if (pathname === "/organization-dimensions" && search) {
    const params = new URLSearchParams(search);
    const section = params.get("section");
    if (section === "business-units") return "Business Units";
    if (section === "departments") return "Departments";
    if (section === "locations") return "Locations";
  }

  if (exactTitles[pathname]) return exactTitles[pathname];
  for (const [pattern, title] of detailRules) {
    const match = pathname.match(pattern);
    if (match) return title(match);
  }

  const segment = pathname.split("/").filter(Boolean).at(-1) ?? "Workspace";
  return segment.replaceAll("-", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}

export function workspaceTabGroup(pathname: string): string | undefined {
  if (!/\/\d+$/.test(pathname)) return undefined;
  return `detail:${pathname.replace(/\/\d+$/, "/:id")}`;
}
