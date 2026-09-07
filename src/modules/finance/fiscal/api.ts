import api from "@/api/client";

export type FiscalAccountListParams = {
  page?: number;
  page_size?: number;
  search?: string;
  category?: string;
  is_active?: boolean;
  is_header?: boolean;
  sort_by?: string;
  sort_order?: "asc" | "desc";
};

export type FiscalAccount = {
  id: number;
  code: string;
  name: string;
  category: string;
  parent_code: string | null;
  is_header: boolean;
  is_active: boolean;
  sort_order: number;
  klasifikasi_fiskal: string | null;
  created_at: string;
  updated_at: string;
};

export type FiscalAccountPayload = {
  code?: string;
  name?: string;
  category?: string;
  parent_code?: string | null;
  is_header?: boolean;
  is_active?: boolean;
  sort_order?: number;
};

export type FiscalAccountPage = {
  items: FiscalAccount[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export interface SptReportParams {
  tax_year: number;
  location_id?: number;
  department_id?: number;
  business_unit_id?: number;
  kompensasi_kerugian?: number;
}

export interface TaxProfile {
  id?: number;
  tax_year?: number;
  npwp?: string | null;
  company_name?: string | null;
  address?: string | null;
  city?: string | null;
  klu?: string | null;
  phone?: string | null;
  email?: string | null;
  representative_name?: string | null;
}

export interface TaxCreditCreate {
  tax_year: number;
  credit_type: "PPh 22" | "PPh 23" | "PPh 24" | "PPh 25" | "OTHER";
  amount: number;
  payment_date?: string | null;
  description?: string | null;
  counterparty_npwp?: string | null;
  counterparty_name?: string | null;
}

export type FiscalBalanceSheetParams = {
  fiscal_year: number;
  department_id?: number;
  location_id?: number;
};

export type FiscalMapping = {
  id: number;
  fiscal_account_id: number;
  fiscal_code: string;
  fiscal_name: string;
  commercial_account_id: number;
  commercial_code: string;
  commercial_name: string;
};

export type FiscalMappingPage = {
  items: FiscalMapping[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export type FiscalLinkedAccount = {
  id: number;
  commercial_code: string;
  commercial_name: string;
  account_type: string;
  mapping_id: number | null;
  fiscal_account_id: number | null;
  fiscal_code: string | null;
  fiscal_name: string | null;
  klasifikasi_fiskal: string | null;
};

export type FiscalLinkedAccountPage = {
  items: FiscalLinkedAccount[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
};

export const fiscalApi = {
  accounts: (params: FiscalAccountListParams = {}) => api.get("/fiscal/accounts", { params }),
  account: (id: number) => api.get(`/fiscal/accounts/${id}`),
  createAccount: (payload: FiscalAccountPayload) => api.post("/fiscal/accounts", payload),
  updateAccount: (id: number, payload: FiscalAccountPayload) => api.patch(`/fiscal/accounts/${id}`, payload),
  deleteAccount: (id: number) => api.delete(`/fiscal/accounts/${id}`),
  categories: () => api.get("/fiscal/categories"),
  mappings: (params: Record<string, unknown> = {}) => api.get("/fiscal/mappings", { params }),
  linkedCoa: (params: Record<string, unknown> = {}) => api.get("/fiscal/linked-coa", { params }),
  unmappedCommercial: (params: Record<string, unknown> = {}) => api.get("/fiscal/mappings/unmapped-commercial", { params }),
  createMapping: (payload: { fiscal_account_id: number; commercial_account_id: number }) => api.post("/fiscal/mappings", payload),
  deleteMapping: (id: number) => api.delete(`/fiscal/mappings/${id}`),
  reconciliation: (params: { date_from: string; date_to: string; location_id?: number; department_id?: number; business_unit_id?: number }) => api.get("/fiscal/reconciliation", { params }),
  fiscalBalanceSheet: (params: FiscalBalanceSheetParams) => api.get("/fiscal-balance-sheet", { params }),
  exportBalanceSheet: (params: FiscalBalanceSheetParams, format: "xlsx" | "csv") => api.get("/fiscal-balance-sheet/export", { params: { ...params, format }, responseType: "blob" }),
  sptReport: (params: SptReportParams) => api.get("/spt-1771/report", { params }),
  sptProfile: (tax_year: number) => api.get("/spt-1771/profile", { params: { tax_year } }),
  sptUpsertProfile: (tax_year: number, payload: Partial<TaxProfile>) => api.put("/spt-1771/profile", payload, { params: { tax_year } }),
  sptCredits: (tax_year: number) => api.get("/spt-1771/credits", { params: { tax_year } }),
  sptCreateCredit: (payload: TaxCreditCreate) => api.post("/spt-1771/credits", payload),
  sptDeleteCredit: (id: number) => api.delete(`/spt-1771/credits/${id}`),
};