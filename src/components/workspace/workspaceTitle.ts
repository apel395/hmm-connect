const exactTitles: Record<string, string> = {
  "/dashboard": "Dashboard",
  "/executive-view": "Executive View",
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
  "/pos/operations": "POS Outlet Operations",
  "/pos/sales": "POS Sales",
  "/reports/purchasing": "Purchasing Reports",
  "/products": "Catering Buy Items",
  "/hotel-items": "Hotel Buy Items",
  "/sell-items": "Catering Sell Items",
  "/hotel-sell-items": "Hotel Sell Items",
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
  "/chart-of-accounts": "Chart of Accounts",
  "/posting-rules": "Direct COA Setup",
  "/fiscal-periods": "Accounting Periods",
  "/finance/fiscal/coa": "Fiscal COA",
  "/finance/fiscal/reconciliation": "Fiscal Reconciliation",
  "/finance/fiscal/lampiran-1d": "Lampiran 1D",
  "/finance/fiscal/spt-1771": "SPT Tahunan 1771",
  "/finance/fiscal/periods": "Accounting Periods",
  "/finance/payment-vouchers": "Payment Vouchers",
  "/fiscal/coa": "Fiscal COA",
  "/fiscal/reconciliation": "Fiscal Reconciliation",
  "/fiscal/lampiran-1d": "Lampiran 1D",
  "/fiscal/spt-1771": "SPT Tahunan 1771",
  "/fiscal/periods": "Accounting Periods",
  "/finance-setup/opening-balances": "Opening Balances",
  "/finance-setup/accounting-periods": "Accounting Periods",
  "/opening-balances": "Opening Balances",
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

export function workspaceTabGroup(pathname: string, search = ""): string {
  // Query changes are a view of the same module/document, never another tab.
  if (/\/\d+(?:\/edit)?$/.test(pathname)) return `document:${pathname.replace(/\/edit$/, "")}`;
  const section = pathname === "/organization-dimensions" ? new URLSearchParams(search).get("section") : null;
  return `module:${pathname}${section ? `:${section}` : ""}`;
}
