import api from "@/api/client";
import * as XLSX from "xlsx";

export interface TrialBalanceFilters {
  date_from: string;
  date_to: string;
  page?: number;
  page_size?: number;
  search?: string;
  account_type?: string;
  account_id?: number;
  parent_account_id?: number;
  include_zero_balance?: boolean;
  include_inactive?: boolean;
  location_id?: number;
  department_id?: number;
  business_unit_id?: number;
  sort_by?: string;
  sort_order?: "asc" | "desc";
}

export interface TrialBalanceRow {
  account_id: number;
  account_code: string;
  account_name: string;
  account_type: string;
  normal_balance: string;
  parent_account_id: number | null;
  parent_account_code: string | null;
  parent_account_name: string | null;
  opening_balance: string;
  opening_debit: string;
  opening_credit: string;
  period_debit: string;
  period_credit: string;
  period_total: string;
  closing_balance: string;
  closing_debit: string;
  closing_credit: string;
  status: "NORMAL" | "ABNORMAL";
}

export interface TrialBalanceResponse {
  items: TrialBalanceRow[];
  summary: Record<string, string | number | boolean>;
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export async function getTrialBalance(params: TrialBalanceFilters) {
  return (await api.get<TrialBalanceResponse>("/trial-balance", { params })).data;
}

export async function exportTrialBalanceXlsx(params: TrialBalanceFilters) {
  // The report is paginated; export every row matching the applied filters.
  const pageSize = 50;
  const first = await getTrialBalance({ ...params, page: 1, page_size: pageSize });
  const items = [...first.items];
  for (let page = 2; page <= first.total_pages; page += 1) {
    const result = await getTrialBalance({ ...params, page, page_size: pageSize });
    items.push(...result.items);
  }

  const rows: (string | number)[][] = [
    ["Trial Balance"],
    ["From", params.date_from, "To", params.date_to],
    ...(params.search ? [["Account search", params.search]] : []),
    ...(params.location_id ? [["Location ID", params.location_id]] : []),
    [],
    ["COA No.", "COA Name", "Opening Debit", "Opening Credit", "Debit Movement", "Credit Movement", "Closing Debit", "Closing Credit", "Status"],
    ...items.map((row) => [
      row.account_code,
      row.account_name,
      Number(row.opening_debit),
      Number(row.opening_credit),
      Number(row.period_debit),
      Number(row.period_credit),
      Number(row.closing_debit),
      Number(row.closing_credit),
      row.status === "ABNORMAL" ? "Abnormal" : "Normal",
    ]),
  ];
  const sheet = XLSX.utils.aoa_to_sheet(rows);
  sheet["!cols"] = [
    { wch: 18 }, { wch: 44 }, { wch: 20 }, { wch: 20 },
    { wch: 20 }, { wch: 20 }, { wch: 20 }, { wch: 16 },
  ];
  const headerRow = rows.findIndex((row) => row[0] === "COA No.");
  for (let r = headerRow + 1; r < rows.length; r += 1) {
    for (let c = 2; c <= 7; c += 1) {
      const cell = sheet[XLSX.utils.encode_cell({ r, c })];
      if (cell) cell.z = "#,##0.00;[Red](#,##0.00)";
    }
  }
  const workbook = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(workbook, sheet, "Trial Balance");
  XLSX.writeFile(workbook, `trial-balance-${params.date_from}-${params.date_to}.xlsx`);
}
