import type { AccountParams } from "./api";
import { getAccounts } from "./api";
import type { ChartOfAccount } from "./types";
import * as XLSX from "xlsx";

export async function loadExportAccounts(params: Omit<AccountParams, "page" | "page_size">) {
  const rows: ChartOfAccount[] = [];
  for (let page = 1; ; page += 1) {
    const result = await getAccounts({ ...params, page, page_size: 100 });
    rows.push(...result.items);
    if (page >= result.total_pages || !result.items.length) break;
  }
  return rows;
}

export function accountWorkbook(accounts: ChartOfAccount[]) {
  const headers = ["Account Code", "Account Name", "Account Type", "Subtype", "Parent Account ID", "Normal Balance", "Posting Account", "Cash Flow Category", "Financial Statement Group", "Status", "System Account", "Description"];
  const rows = accounts.map(account => [
    account.account_code, account.account_name, account.account_type, account.account_subtype,
    account.parent_account_id ?? "", account.normal_balance, account.is_posting ? "Yes" : "No",
    account.cash_flow_category ?? "", account.financial_statement_group ?? "",
    account.is_active ? "Active" : "Archived", account.is_system ? "Yes" : "No", account.description ?? "",
  ]);
  const sheet = XLSX.utils.aoa_to_sheet([headers, ...rows]);
  sheet["!cols"] = [20, 40, 18, 18, 20, 18, 18, 22, 30, 14, 18, 50].map(wch => ({ wch }));
  sheet["!autofilter"] = { ref: sheet["!ref"]! };
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, "Chart of Accounts");
  return workbook;
}

export async function exportAccountsExcel(params: Omit<AccountParams, "page" | "page_size">) {
  const accounts = await loadExportAccounts(params);
  XLSX.writeFile(accountWorkbook(accounts), "chart-of-accounts.xlsx");
  return accounts.length;
}
