import api from "@/api/client";

export type OpeningBalanceAccount = {
  id: number;
  account_code: string;
  account_name: string;
  account_type: string;
  normal_balance: string;
  existing_balance: number;
  existing_debit?: number;
  existing_credit?: number;
};

export type OpeningBalanceLine = {
  account_id: number;
  amount: number;
  balance_type?: string;
};

export const openingBalanceApi = {
  accounts: (fiscal_year: number, location_id?: number) =>
    api.get("/opening-balances/accounts", { params: { fiscal_year, location_id: location_id || undefined } }),
  list: (fiscal_year: number, location_id?: number) =>
    api.get("/opening-balances", { params: { fiscal_year, location_id: location_id || undefined } }),
  preview: (fiscal_year: number, lines: OpeningBalanceLine[]) =>
    api.post("/opening-balances/preview", { fiscal_year, lines }),
  post: (fiscal_year: number, lines: OpeningBalanceLine[], description?: string, location_id?: number) =>
    api.post("/opening-balances", { fiscal_year, lines, description, location_id: location_id || undefined }),
  void: (fiscal_year: number, location_id?: number) =>
    api.delete("/opening-balances", { params: { fiscal_year, location_id: location_id || undefined } }),
};
