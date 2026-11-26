import api from "@/api/client";

/** Backend amounts arrive as numbers or decimal strings. */
export type LedgerAmount = string | number | null | undefined;

/** Query values are serialized by the API client; empty strings are dropped there. */
export interface LedgerQueryParams {
  page?: number;
  page_size?: number;
  search?: string;
  search_type?: string;
  account_id?: string | number;
  account_ids?: string;
  account_from_id?: string | number;
  account_to_id?: string | number;
  date_from?: string;
  date_to?: string;
  reference_type?: string;
  supplier_id?: string | number;
  department_id?: string | number;
  location_id?: string | number;
  business_unit_id?: string | number;
}

export type LedgerListParams = LedgerQueryParams;
export type LedgerPrintParams = LedgerQueryParams;
export type LedgerExportParams = LedgerQueryParams;

export interface LedgerTotals {
  total_debit?: LedgerAmount;
  total_credit?: LedgerAmount;
}

export interface LedgerEntry {
  id: number | string;
  posting_date: string;
  journal_id: number | string;
  journal_number: string;
  account_id: number | string;
  account_code: string;
  account_name: string;
  description?: string | null;
  reference_number?: string | null;
  reference_type?: string | null;
  reference_id?: number | string | null;
  debit?: LedgerAmount;
  credit?: LedgerAmount;
  balance?: LedgerAmount;
  supplier_name?: string | null;
  business_unit_name?: string | null;
  department_name?: string | null;
  location_name?: string | null;
}

export interface LedgerListResponse {
  items: LedgerEntry[];
  total_items: number;
  total_pages: number;
  page: number;
  page_size: number;
  has_next: boolean;
  has_previous: boolean;
  summary?: LedgerTotals;
  totals?: LedgerTotals;
}

export interface LedgerAccountSummaryParams {
  business_unit_id?: number;
  location_id?: number;
  department_id?: number;
  date_from?: string;
  date_to?: string;
}

export interface LedgerAccountSummary {
  opening_balance?: LedgerAmount;
  closing_balance?: LedgerAmount;
  total_debit?: LedgerAmount;
  total_credit?: LedgerAmount;
}

export interface LedgerPrintRow {
  id?: number | string;
  posting_date?: string | null;
  journal_number?: string | null;
  document_number?: string | null;
  document_type?: string | null;
  reference?: string | null;
  description?: string | null;
  location_name?: string | null;
  department_name?: string | null;
  debit?: LedgerAmount;
  credit?: LedgerAmount;
  balance?: LedgerAmount;
}

export interface LedgerPrintAccount {
  account_id: number | string;
  account_code: string;
  account_name: string;
  account_type?: string;
  normal_balance?: string;
  opening_balance?: LedgerAmount;
  closing_balance?: LedgerAmount;
  total_debit?: LedgerAmount;
  total_credit?: LedgerAmount;
  rows?: LedgerPrintRow[];
}

export interface LedgerPrintResponse {
  accounts: LedgerPrintAccount[];
  control?: LedgerTotals;
}

export interface LedgerExportJob {
  job_id: string;
}

export interface ExportJobStatus {
  status: string;
  download_url?: string | null;
  error_message?: string | null;
}

export type LedgerAccountBalance = { account_id: number; account_code: string; account_name: string; normal_balance: string; opening_balance: string | number; total_debit: string | number; total_credit: string | number; closing_balance: string | number };

export interface LedgerAccountBalancesParams {
  account_ids?: string;
  date_from?: string;
  date_to?: string;
  business_unit_id?: string | number;
  location_id?: string | number;
  department_id?: string | number;
}

export interface LedgerAccountBalancesResponse {
  items: LedgerAccountBalance[];
  balance_scope: string;
}

export const listLedger = async (params: LedgerListParams): Promise<LedgerListResponse> =>
  (await api.get<LedgerListResponse>("/general-ledger", { params })).data;

export const getAccountSummary = async (accountId: number, params: LedgerAccountSummaryParams): Promise<LedgerAccountSummary> =>
  (await api.get<LedgerAccountSummary>(`/general-ledger/accounts/${accountId}/summary`, { params })).data;

export const getLedgerPrint = async (params: LedgerPrintParams): Promise<LedgerPrintResponse> =>
  (await api.get<LedgerPrintResponse>("/general-ledger/print", { params })).data;

export const createLedgerExport = async (params: LedgerExportParams): Promise<LedgerExportJob> =>
  (await api.post<LedgerExportJob>("/exports", { export_type: "general_ledger", params })).data;

export const getExport = async (jobId: string): Promise<ExportJobStatus> =>
  (await api.get<ExportJobStatus>(`/exports/${jobId}`)).data;

export const getLedgerAccountBalances = async (params: LedgerAccountBalancesParams): Promise<LedgerAccountBalancesResponse> =>
  (await api.get<LedgerAccountBalancesResponse>("/general-ledger/account-balances", { params })).data;
