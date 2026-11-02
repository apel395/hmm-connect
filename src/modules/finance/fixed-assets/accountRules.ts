import type { AccountLookup } from "@/modules/master/chart-of-accounts/types";
const assetTypes: Record<string, string> = { "100-900-100": "Operating Equipment — Linen", "100-900-101": "Operating Equipment — Chinaware", "100-900-102": "Operating Equipment — Silverware", "100-900-103": "Operating Equipment — Glassware", "100-600-100": "Land", "100-600-101": "Building", "100-600-102": "Mechanical / Electrical", "100-600-103": "Vehicle", "100-600-104": "Furniture, Fixtures & Equipment", "100-600-105": "Inventaris", "100-600-999": "Other fixed assets" };
export const assetType = (code: string) => assetTypes[code] || "Fixed assets";
export const fixedAssetAccount = (account: AccountLookup) => account.account_type === "ASSET" && account.normal_balance === "DEBIT" && account.account_code.startsWith("100-600-");
export const accumulatedDepreciationAccount = (account: AccountLookup) => account.account_type === "ASSET" && account.normal_balance === "CREDIT" && account.account_code.startsWith("100-800");
export const depreciationExpenseAccount = (account: AccountLookup) => account.account_type === "EXPENSE" && account.normal_balance === "DEBIT" && /penyusutan|depresiasi|depreciation/i.test(account.account_name);
export const amortizationAssetAccount = (account: AccountLookup) => account.account_type === "ASSET" && account.normal_balance === "DEBIT" && (account.account_code.startsWith("100-400") || /amort|intangible|tak berwujud|tidak berwujud/i.test(account.account_name));

export const accumulatedAccountCodes: Record<string, string> = {
  "100-600-101": "100-800-100", "100-600-102": "100-800-101",
  "100-600-103": "100-800-102", "100-600-104": "100-800-103",
  "100-600-105": "100-800-104", "100-600-999": "100-800-999",
};
