import api from "@/api/client";
import type { StoreIssue, StoreIssuePayload, StoreRequest, StoreRequestPayload } from "./types";

export const storeRequestApi = {
  list: (params: { page?: number; page_size?: number; status?: string; search?: string } = {}) => api.get("/store-requests", { params }),
  detail: (id: number) => api.get<StoreRequest>(`/store-requests/${id}`),
  create: (payload: StoreRequestPayload) => api.post<StoreRequest>("/store-requests", payload),
  update: (id: number, payload: StoreRequestPayload) => api.patch<StoreRequest>(`/store-requests/${id}`, payload),
  submit: (id: number) => api.post<StoreRequest>(`/store-requests/${id}/submit`),
  approve: (id: number, comment?: string) => api.post<StoreRequest>(`/store-requests/${id}/approve`, { comment }),
  reject: (id: number, comment: string) => api.post<StoreRequest>(`/store-requests/${id}/reject`, { comment }),
  createIssue: (id: number, payload: StoreIssuePayload) => api.post<StoreIssue>(`/store-requests/${id}/issues`, payload),
  postIssue: (issueId: number) => api.post<StoreIssue>(`/store-requests/issues/${issueId}/post`),
};
