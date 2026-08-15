import api from "@/api/client";

export type RequisitionListParams = {
  scope?: "active" | "history" | "all";
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
};

export const requisitionApi = {
  list: (params: RequisitionListParams = {}) => api.get("/purchase-requisitions", { params }),
  detail: (id: number) => api.get(`/purchase-requisitions/${id}`),
  create: (payload: any) => api.post("/purchase-requisitions", payload),
  update: (id: number, payload: any) => api.put(`/purchase-requisitions/${id}`, payload),
  reopen: (id: number) => api.post(`/purchase-requisitions/${id}/reopen`),
  submit: (id: number) => api.post(`/purchase-requisitions/${id}/submit`),
  approve: (id: number, comment?: string) => api.post(`/purchase-requisitions/${id}/approve`, { comment }),
  reject: (id: number, comment?: string) => api.post(`/purchase-requisitions/${id}/reject`, { comment }),
  cancel: (id: number) => api.patch(`/purchase-requisitions/${id}/cancel`),
  traceability: (id: number) => api.get(`/traceability/purchase-requisitions/${id}`),
  convertToPO: (id: number, supplier_id: number) => api.post(`/purchase-requisitions/${id}/convert-to-po`, { supplier_id }),
};

export default requisitionApi;
