import api from "@/api/client";
import type { AccountLookup, AccountPage, AccountPayload, AccountSubtype, AccountType, ChartOfAccount, ChartOfAccountNode, NormalBalance } from "./types";

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
export async function getAccountLookup(params: {
  search?: string;
  page?: number;
  page_size?: number;
  account_type?: AccountType;
  account_subtype?: AccountSubtype | AccountSubtype[];
  is_posting?: boolean;
  is_active?: boolean;
} = {}) {
  const { data } = await api.get<AccountLookup[]>("/chart-of-accounts/lookup", {
    params: {
      ...params,
      page: params.page ?? 1,
      page_size: Math.min(params.page_size ?? 50, 50),
    },
  });
  return data;
}

export async function getAllAccountLookup(params: {
  search?: string;
  account_type?: AccountType;
  account_subtype?: AccountSubtype | AccountSubtype[];
  is_posting?: boolean;
  is_active?: boolean;
} = {}) {
  const pageSize = 50;
  const allAccounts: AccountLookup[] = [];
  let page = 1;

  while (true) {
    const accounts = await getAccountLookup({
      ...params,
      page,
      page_size: pageSize,
    });

    allAccounts.push(...accounts);

    if (accounts.length < pageSize) break;
    page += 1;
  }

  return allAccounts;
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
