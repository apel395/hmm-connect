import api from "@/api/interceptor";

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

type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type APSummaryResponse = Page<APSupplierSummary> & {
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

export const apReportingApi = {
  summary: async (page = 1, pageSize = 20, business_unit_id?:number) =>
    (await api.get<APSummaryResponse>("/ap-reporting/summary", { params: { page, page_size: pageSize,business_unit_id } })).data,
  detail: async (page = 1, pageSize = 20, business_unit_id?:number) =>
    (await api.get<Page<APDetailRow>>("/ap-reporting/detail", { params: { page, page_size: pageSize,business_unit_id } })).data,
};
