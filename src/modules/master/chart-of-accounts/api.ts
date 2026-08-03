import api from "@/api/client";
import type { AccountLookup, AccountPage, AccountPayload, AccountType, ChartOfAccount, ChartOfAccountNode, NormalBalance } from "./types";

export interface AccountParams {
  page: number;
  page_size: number;
  search?: string;
  account_type?: AccountType;
  normal_balance?: NormalBalance;
  is_posting?: boolean;
  is_active?: boolean;
  sort_by: string;
  sort_order: "asc" | "desc";
}

export async function getAccounts(params: AccountParams) {
  const { data } = await api.get<AccountPage>("/chart-of-accounts", { params });
  return data;
}
export async function getAccountTree() {
  const { data } = await api.get<ChartOfAccountNode[]>("/chart-of-accounts/tree");
  return data;
}
export async function getAccountLookup(params: { account_type?: AccountType; is_posting?: boolean; is_active?: boolean } = {}) {
  const { data } = await api.get<AccountLookup[]>("/chart-of-accounts/lookup", { params });
  return data;
}
export async function createAccount(payload: AccountPayload) {
  const { data } = await api.post<ChartOfAccount>("/chart-of-accounts", payload);
  return data;
}
export async function updateAccount(id: number, payload: Partial<AccountPayload>) {
  const { data } = await api.patch<ChartOfAccount>(`/chart-of-accounts/${id}`, payload);
  return data;
}
export async function archiveAccount(id: number) {
  const { data } = await api.patch<ChartOfAccount>(`/chart-of-accounts/${id}/archive`);
  return data;
}
export async function restoreAccount(id: number) {
  const { data } = await api.patch<ChartOfAccount>(`/chart-of-accounts/${id}/restore`);
  return data;
}
