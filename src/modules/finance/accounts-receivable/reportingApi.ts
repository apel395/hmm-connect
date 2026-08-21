import api from "@/api/interceptor";

export type ARStatus = "PAID" | "PARTIALLY_PAID" | "UNPAID";
export type AgingBucket = "current" | "1_30" | "31_60" | "61_90" | "over_90";

export type Page<T> = {
  items: T[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type CustomerSummary = {
  customer_id: number;
  customer_code?: string | null;
  customer_name?: string | null;
  gross_amount: number;
  received_amount: number;
  outstanding_amount: number;
  invoice_count: number;
  open_invoice_count: number;
  overdue_invoice_count: number;
  status: ARStatus;
};

export type ARDetail = {
  invoice_id: number;
  invoice_number: string;
  customer_id: number;
  customer_code?: string | null;
  customer_name?: string | null;
  invoice_date: string;
  due_date?: string | null;
  gross_amount: number;
  received_amount: number;
  outstanding_amount: number;
  status: ARStatus;
  days_overdue: number;
  aging_bucket: AgingBucket;
};

export type ARSummary = Page<CustomerSummary> & {
  metrics: {
    gross_receivables: number;
    total_receipts: number;
    outstanding_receivables: number;
    overdue_receivables: number;
    customer_count: number;
    invoice_count: number;
  };
};

export type ARAgingRow = {
  customer_id: number;
  customer_code?: string | null;
  customer_name?: string | null;
  outstanding_amount: number;
} & Record<AgingBucket, number>;

export type ARAging = Page<ARAgingRow> & {
  as_of_date: string;
  total_outstanding: number;
  buckets: Record<AgingBucket, {
    amount: number;
    invoice_count: number;
    customer_count: number;
  }>;
};

const params = (page: number, pageSize: number, search: string) => ({
  page,
  page_size: pageSize,
  search: search.trim() || undefined,
});

export const arReportingApi = {
  summary: async (page = 1, pageSize = 20, search = "") =>
    (await api.get<ARSummary>("/ar-reporting/summary", { params: params(page, pageSize, search) })).data,
  detail: async (page = 1, pageSize = 20, search = "") =>
    (await api.get<Page<ARDetail>>("/ar-reporting/detail", { params: params(page, pageSize, search) })).data,
  aging: async (page = 1, pageSize = 20, search = "") =>
    (await api.get<ARAging>("/ar-reporting/aging", { params: params(page, pageSize, search) })).data,
};
