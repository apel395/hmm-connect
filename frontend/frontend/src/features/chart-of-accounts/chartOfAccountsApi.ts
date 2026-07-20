import api from "../../api/client";

export interface ChartOfAccount {
  id: number;
  account_number: string;
  account_name: string;
  account_type: string;
  is_active: boolean;
}

export async function getChartOfAccounts(): Promise<ChartOfAccount[]> {
  const response = await api.get<ChartOfAccount[]>("/chart-of-accounts");
  return response.data;
}
