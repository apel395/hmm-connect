import api from "@/api/client";

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

export const taxApi = {
  report: (params: SptReportParams) => api.get("/spt-1771/report", { params }),
  profile: (tax_year: number) => api.get("/spt-1771/profile", { params: { tax_year } }),
  upsertProfile: (tax_year: number, payload: Partial<TaxProfile>) => api.put("/spt-1771/profile", payload, { params: { tax_year } }),
  credits: (tax_year: number) => api.get("/spt-1771/credits", { params: { tax_year } }),
  createCredit: (payload: TaxCreditCreate) => api.post("/spt-1771/credits", payload),
  deleteCredit: (id: number) => api.delete(`/spt-1771/credits/${id}`),
};
