import api from "@/api/client";

export interface FinanceDashboardFilters {
  as_of_date?: string;
  date_from: string;
  date_to: string;
  location_id?: string;
  department_id?: string;
  cash_account_id?: string;
  currency?: string;
  business_unit_id?: string;
}

export const getFinanceDashboard = async (filters: FinanceDashboardFilters) =>
  (await api.get("/dashboard/finance", {
    params: Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== "" && value != null)),
  })).data;
