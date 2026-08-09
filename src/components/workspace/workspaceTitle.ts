const exactTitles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/finance-dashboard": "Finance Dashboard",
  "/purchase-requisitions": "Purchase Requisitions",
  "/purchase-orders": "Purchase Orders",
  "/receiving": "Receiving",
  "/purchasing-documents": "Purchasing Documents",
  "/inventory": "Inventory",
  "/inventory/movements": "Stock Movement",
  "/products": "Items",
  "/suppliers": "Suppliers",
  "/warehouses": "Warehouses",
  "/accounts-payable": "AP Overview",
  "/accounts-payable/aging": "AP Aging",
  "/accounts-payable/invoices": "Supplier Invoices",
  "/accounts-payable/payments": "Payments",
  "/supplier-invoices": "Supplier Invoices",
  "/payments": "Payments",
  "/supplier-adjustments": "Credit / Debit Notes",
  "/journal-entries": "Journal",
  "/cash-accounts": "Cash & Bank Accounts",
  "/bank-transfers": "Bank Transfers",
  "/bank-reconciliations": "Bank Reconciliation",
  "/chart-of-accounts": "Chart of Accounts",
  "/posting-rules": "Posting Rules",
  "/fiscal-periods": "Fiscal Periods",
  "/fixed-assets": "Fixed Assets",
  "/fixed-assets/amortization": "Amortization",
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
  return segment
    .replaceAll("-", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}
