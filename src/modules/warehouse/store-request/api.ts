import api from "@/api/client";
import type { StoreIssue, StoreIssuePayload, StoreRequest, StoreRequestPayload } from "./types";

export const storeRequestApi = {
  list: (params: { page?: number; page_size?: number; status?: string; search?: string } = {}) => api.get("/store-requests", { params }),
  detail: (id: number) => api.get<StoreRequest>(`/store-requests/${id}`),
  availability: async (warehouseId: number, productIds: number[]) => {
    const ids = [...new Set(productIds)];
    const response = await api.get<Array<{ product_id: number; available_stock: number }>>("/store-requests/availability", {
      params: { warehouse_id: warehouseId, product_ids: ids },
      // FastAPI reads repeated product_ids, not Axios's default product_ids[].
      paramsSerializer: { indexes: null },
    });
    if (!Array.isArray(response.data) || ids.some(id => !response.data.some(row => row.product_id === id && row.available_stock !== null && row.available_stock !== undefined && Number.isFinite(Number(row.available_stock))))) {
      throw new Error("Warehouse stock could not be read. Retry the stock check.");
    }
    return response;
  },
  create: (payload: StoreRequestPayload) => api.post<StoreRequest>("/store-requests", payload),
  update: (id: number, payload: StoreRequestPayload) => api.patch<StoreRequest>(`/store-requests/${id}`, payload),
  submit: (id: number) => api.post<StoreRequest>(`/store-requests/${id}/submit`),
  approve: (id: number, comment?: string) => api.post<StoreRequest>(`/store-requests/${id}/approve`, { comment }),
  reject: (id: number, comment: string) => api.post<StoreRequest>(`/store-requests/${id}/reject`, { comment }),
  createIssue: (id: number, payload: StoreIssuePayload) => api.post<StoreIssue>(`/store-requests/${id}/issues`, payload),
  postIssue: (issueId: number) => api.post<StoreIssue>(`/store-requests/issues/${issueId}/post`),
};
