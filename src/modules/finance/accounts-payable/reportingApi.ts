import api from "@/api/interceptor";
import type { FinancePage } from "@/modules/finance/types";

export type APStatus = "PAID" | "PARTIALLY_PAID" | "UNPAID";

export type APSupplierSummary = {
  supplier_id: number;
  supplier_code?: string | null;
  supplier_name?: string | null;
  gross_amount: number;
  paid_amount: number;
  adjustment_amount: number;
  outstanding_amount: number;
  invoice_count: number;
  open_invoice_count: number;
  status: APStatus;
};

export type APDetailRow = {
  invoice_id: number;
  invoice_number: string;
  supplier_invoice_number: string;
  supplier_id: number;
  supplier_code?: string | null;
  supplier_name?: string | null;
  invoice_date: string;
  due_date?: string | null;
  gross_amount: number;
  paid_amount: number;
  adjustment_amount: number;
  outstanding_amount: number;
  status: APStatus;
  last_payment_date?: string | null;
  days_overdue: number;
  aging_bucket: "current" | "1_30" | "31_60" | "61_90" | "over_90";
};

export type APSummaryResponse = FinancePage<APSupplierSummary> & {
  metrics: {
    gross_payables: number;
    total_payments: number;
    total_adjustments: number;
    outstanding_payables: number;
    supplier_count: number;
    invoice_count: number;
  };
  status_counts: Record<APStatus, number>;
};

export type APReportingQuery = {
  page?: number;
  pageSize?: number;
  search?: string;
  status?: APStatus;
  businessUnitId?: number;
};

const params = ({ page = 1, pageSize = 50, search = "", status, businessUnitId }: APReportingQuery) => ({
  page,
  page_size: pageSize,
  business_unit_id: businessUnitId || undefined,
  search: search.trim() || undefined,
  status: status || undefined,
});

export const apReportingApi = {
  summary: async (query: APReportingQuery = {}) =>
    (await api.get<APSummaryResponse>("/ap-reporting/summary", { params: params(query) })).data,
  detail: async (query: APReportingQuery = {}) =>
    (await api.get<FinancePage<APDetailRow>>("/ap-reporting/detail", { params: params(query) })).data,
};
