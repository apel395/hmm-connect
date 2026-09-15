import api from "@/api/client";

export type PosPaymentMethod = "CASH" | "CARD" | "BANK_TRANSFER";
export type PosTransactionType = "POS" | "INVOICE";

export type PosListParams = {
  page?: number;
  page_size?: number;
  status?: string;
  warehouse_id?: number;
  date_from?: string;
  date_to?: string;
  search?: string;
};

export type PosItemIn = {
  product_id: number;
  quantity: number;
  unit_price?: number | null;
};

export type PosCreatePayload = {
  warehouse_id: number;
  transaction_type?: PosTransactionType;
  table_number?: string | null;
  queue_number?: string | null;
  sale_date?: string | null;
  customer_id?: number | null;
  business_unit_id?: number | null;
  location_id?: number | null;
  department_id?: number | null;
  notes?: string | null;
  items: PosItemIn[];
};

export type PosUpdatePayload = {
  transaction_type?: PosTransactionType;
  table_number?: string | null;
  queue_number?: string | null;
  sale_date?: string | null;
  customer_id?: number | null;
  notes?: string | null;
  items: PosItemIn[];
};

export type PosMetadataPayload = {
  transaction_type: PosTransactionType;
  table_number?: string | null;
  queue_number?: string | null;
};

export type PosPostPayload = {
  payment_method: PosPaymentMethod;
  payment_received?: number | null;
  discount_amount?: number | null;
};

export type PosVoidPayload = {
  reason?: string | null;
};

export const posApi = {
  products: (params: Record<string, unknown> = {}) => api.get("/pos/products", { params }),
  list: (params: PosListParams = {}) => api.get("/pos", { params }),
  detail: (id: number) => api.get(`/pos/${id}`),
  create: (payload: PosCreatePayload) => api.post("/pos", payload),
  update: (id: number, payload: PosUpdatePayload) => api.put(`/pos/${id}`, payload),
  metadata: (id: number, payload: PosMetadataPayload) => api.patch(`/pos-metadata/${id}`, payload),
  post: (id: number, payload: PosPostPayload) => api.post(`/pos/${id}/post`, payload),
  void: (id: number, payload: PosVoidPayload = {}) => api.post(`/pos/${id}/void`, payload),
  print: (id: number) => api.get(`/pos/${id}/print`),
};