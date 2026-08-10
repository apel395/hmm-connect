import api from "@/api/client";

export interface PurchaseOrderItemPayload {
  product_id?: number;
  description?: string;
  uom?: string;
  quantity: number;
  unit_price: number;
  purchase_requisition_item_id?: number | null;
}

export interface PurchaseOrderCreatePayload {
  business_unit_id?: number;
  supplier_id: number;
  department_id?: number;
  location_id?: number;
  order_date?: string;
  expected_date?: string;
  expiry_date?: string | null;
  notes?: string;
  purchase_requisition_ids?: number[];
  items: PurchaseOrderItemPayload[];
}

export const purchaseOrderApi = {
  list: (params: { scope?: "active" | "history" | "all"; status?: string; page?: number; page_size?: number } = {}) => api.get("/purchase-orders", { params }),
  detail: (id: number) => api.get(`/purchase-orders/${id}`),
  create: (payload: PurchaseOrderCreatePayload) => api.post("/purchase-orders", payload),
  update: (id: number, payload: PurchaseOrderCreatePayload) => api.put(`/purchase-orders/${id}`, payload),
  reopen: (id: number) => api.post(`/purchase-orders/${id}/reopen`),
  submit: (id: number) => api.post(`/purchase-orders/${id}/submit`),
  approve: (id: number, comment = "") => api.post(`/purchase-orders/${id}/approve`, { comment }),
  reject: (id: number, comment = "") => api.post(`/purchase-orders/${id}/reject`, { comment }),
  cancel: (id: number) => api.post(`/purchase-orders/${id}/cancel`),
  delete: (id: number) => api.delete(`/purchase-orders/${id}`),
  approvedPurchaseRequisitions: () => api.get("/purchase-requisitions/eligible-for-po"),
};

export default purchaseOrderApi;
