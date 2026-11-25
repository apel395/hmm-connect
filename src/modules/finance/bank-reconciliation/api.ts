import api from "@/api/client";
import type { FinancePage } from "@/modules/finance/types";

export type ReconciliationStatus = "DRAFT" | "IN_PROGRESS" | "COMPLETED" | "VOID";
export type MatchType = "MANUAL" | "AUTO_SUGGESTED";

export type ReconciliationListParams = {
  page: number;
  page_size: number;
  status: string;
  account_id: string;
  search: string;
};

export type ReconciliationAccount = {
  id: number;
  account_code: string;
  account_name: string;
};

export type ReconciliationAllowedActions = {
  match?: boolean;
  complete?: boolean;
  void?: boolean;
  [action: string]: boolean | undefined;
};

/** Shared shape of the list rows and the detail response. */
export type Reconciliation = {
  id: number;
  reconciliation_number: string;
  account_id: number;
  account_code: string;
  account_name: string;
  status: ReconciliationStatus;
  statement_start_date: string;
  statement_end_date: string;
  statement_opening_balance: number | string | null;
  statement_closing_balance: number | string | null;
  system_opening_balance: number | string | null;
  system_closing_balance: number | string | null;
  matched_amount: number | string | null;
  unmatched_statement_amount: number | string | null;
  unmatched_system_amount: number | string | null;
  difference: number | string | null;
  matched_count: number;
  unmatched_count: number;
  allowed_actions?: ReconciliationAllowedActions;
  [key: string]: unknown;
};

export type CreateReconciliationPayload = {
  account_id: number;
  statement_start_date: string;
  statement_end_date: string;
  statement_opening_balance: string;
  statement_closing_balance: string;
  notes: string;
};

export type ReconciliationMatch = {
  id: number;
  [key: string]: unknown;
};

export type StatementLine = {
  id: number;
  transaction_date: string;
  description: string;
  reference_number?: string | null;
  debit: number | string | null;
  credit: number | string | null;
  match_status: string;
  matches?: ReconciliationMatch[];
};

export type SystemTransaction = {
  journal_line_id: number;
  posting_date: string;
  journal_number: string;
  source_route: string;
  reference_type: string;
  description: string;
  debit: number | string | null;
  credit: number | string | null;
  remaining_amount: number | string | null;
  outstanding_type: string;
};

export type StatementUploadMapping = Record<string, unknown>;

export type StatementUploadPreview = {
  rows_detected: number;
  rows_accepted: number;
  duplicates: number;
  errors: unknown[];
  [key: string]: unknown;
};

export type AutoMatchSuggestion = {
  statement_line_id: number;
  journal_line_id: number;
  matched_amount: number;
  match_type?: MatchType;
  [key: string]: unknown;
};

export type AutoMatchResult = {
  suggestions?: AutoMatchSuggestion[];
  [key: string]: unknown;
};

export type MatchAllocation = {
  statement_line_id: number;
  journal_line_id: number;
  matched_amount: number;
  match_type: MatchType;
};

export type AdjustmentType =
  | "BANK_FEE"
  | "BANK_INTEREST"
  | "TAX_WITHHOLDING"
  | "OTHER_BANK_ADJUSTMENT";

export type CreateAdjustmentPayload = {
  statement_line_id: number;
  adjustment_type: AdjustmentType;
  posting_date: string;
  description: string;
  debit_account_id: number;
  credit_account_id: number;
  amount: number;
  notes: string;
};

export type AdjustmentResult = {
  route: string;
  [key: string]: unknown;
};

export type ReconciliationActionResult = {
  id?: number;
  status?: ReconciliationStatus;
  success?: boolean;
  [key: string]: unknown;
};

export const listReconciliations=async(params:ReconciliationListParams)=>(await api.get<FinancePage<Reconciliation>>("/bank-reconciliations",{params})).data;
export const getReconciliation=async(id:number)=>(await api.get<Reconciliation>(`/bank-reconciliations/${id}`)).data;
export const getReconciliationAccounts=async()=>(await api.get<ReconciliationAccount[]>("/bank-reconciliations/accounts")).data;
export const createReconciliation=async(data:CreateReconciliationPayload)=>(await api.post<Reconciliation>("/bank-reconciliations",data)).data;
export const getStatementLines=async(id:number)=>(await api.get<StatementLine[]>(`/bank-reconciliations/${id}/statement-lines`)).data;
export const getSystemTransactions=async(id:number)=>(await api.get<SystemTransaction[]>(`/bank-reconciliations/${id}/system-transactions`)).data;
export const uploadStatement=async(id:number,file:File,mapping:StatementUploadMapping,preview=false)=>{const form=new FormData();form.append("file",file);form.append("mapping_json",JSON.stringify(mapping));form.append("preview",String(preview));return(await api.post<StatementUploadPreview>(`/bank-reconciliations/${id}/upload-statement`,form)).data};
export const autoMatch=async(id:number,confirm_suggested=false)=>(await api.post<AutoMatchResult>(`/bank-reconciliations/${id}/auto-match`,{date_tolerance_days:3,confirm_suggested})).data;
export const createMatches=async(id:number,allocations:MatchAllocation[])=>(await api.post<ReconciliationActionResult>(`/bank-reconciliations/${id}/matches`,{allocations})).data;
export const removeMatch=async(id:number,matchId:number)=>(await api.delete<ReconciliationActionResult>(`/bank-reconciliations/${id}/matches/${matchId}`)).data;
export const createAdjustment=async(id:number,data:CreateAdjustmentPayload)=>(await api.post<AdjustmentResult>(`/bank-reconciliations/${id}/create-adjustment`,data)).data;
export const completeReconciliation=async(id:number)=>(await api.post<ReconciliationActionResult>(`/bank-reconciliations/${id}/complete`)).data;
export const voidReconciliation=async(id:number)=>(await api.post<ReconciliationActionResult>(`/bank-reconciliations/${id}/void`)).data;
