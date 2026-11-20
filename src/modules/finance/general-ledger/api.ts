import api from "@/api/client";

export const listLedger = async (params: any) => (await api.get("/general-ledger", { params })).data;
export const getAccountSummary = async (accountId: number, params: any) => (await api.get(`/general-ledger/accounts/${accountId}/summary`, { params })).data;
export const getLedgerPrint = async (params: any) => (await api.get("/general-ledger/print", { params })).data;
export const createLedgerExport = async (params: any) => (await api.post("/exports", { export_type: "general_ledger", params })).data;
export const getExport = async (jobId: string) => (await api.get(`/exports/${jobId}`)).data;
export type LedgerAccountBalance = { account_id: number; account_code: string; account_name: string; normal_balance: string; opening_balance: string | number; total_debit: string | number; total_credit: string | number; closing_balance: string | number };
export const getLedgerAccountBalances = async (params: Record<string, string | number | undefined>): Promise<{ items: LedgerAccountBalance[]; balance_scope: string }> =>
  (await api.get("/general-ledger/account-balances", { params })).data;
