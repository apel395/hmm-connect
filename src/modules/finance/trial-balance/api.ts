import api from "@/api/client";

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
  opening_debit: string;
  opening_credit: string;
  period_debit: string;
  period_credit: string;
  closing_debit: string;
  closing_credit: string;
  is_abnormal_balance: boolean;
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

export async function exportTrialBalance(params: TrialBalanceFilters, format: "xlsx" | "csv") {
  const response = await api.get("/trial-balance/export", { params: { ...params, format }, responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = `trial-balance-${params.date_from}-${params.date_to}.${format}`;
  link.click();
  URL.revokeObjectURL(url);
}
