import api from "@/api/client";

export interface BankAccount {
  id: number;
  bank_name: string;
  account_name: string;
  account_number: string;
  account_holder?: string | null;
  currency: string;
  business_unit_id: number;
  business_unit_name?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  coa_account_id: number;
  coa_account_code?: string | null;
  coa_account_name?: string | null;
  is_active: boolean;
}

export const listBankAccounts = async (activeOnly = false) =>
  (await api.get<BankAccount[]>("/bank-accounts", { params: { active_only: activeOnly } })).data;

export const saveBankAccount = async (payload: Partial<BankAccount> & { id?: number }) => {
  const { id, ...data } = payload;
  return id
    ? (await api.patch<BankAccount>(`/bank-accounts/${id}`, data)).data
    : (await api.post<BankAccount>("/bank-accounts", data)).data;
};
