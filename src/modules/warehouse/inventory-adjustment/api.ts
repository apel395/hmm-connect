import api from "@/api/client";

export type StockAdjustmentListParams = {
  page?: number;
  page_size?: number;
  status?: string;
  warehouse_id?: number;
  date_from?: string;
  date_to?: string;
  search?: string;
};

export type StockAdjustmentItemIn = {
  product_id: number;
  adjusted_quantity: number;
  reason?: string | null;
};

export type StockAdjustmentCreatePayload = {
  warehouse_id: number;
  adjustment_date?: string | null;
  business_unit_id?: number | null;
  location_id?: number | null;
  department_id?: number | null;
  reason: string;
  notes?: string | null;
  items?: StockAdjustmentItemIn[];
};

export type StockAdjustmentUpdatePayload = {
  adjustment_date?: string | null;
  reason: string;
  notes?: string | null;
  items: StockAdjustmentItemIn[];
};

export const stockAdjustmentApi = {
  list: (params: StockAdjustmentListParams = {}) => api.get("/stock-adjustments", { params }),
  detail: (id: number) => api.get(`/stock-adjustments/${id}`),
  create: (payload: StockAdjustmentCreatePayload) => api.post("/stock-adjustments", payload),
  update: (id: number, payload: StockAdjustmentUpdatePayload) => api.put(`/stock-adjustments/${id}`, payload),
  post: (id: number) => api.post(`/stock-adjustments/${id}/post`),
  void: (id: number) => api.post(`/stock-adjustments/${id}/void`),
};