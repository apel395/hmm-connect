import api from "@/api/client";
import type {
  PurchasingDocument,
  PurchasingDocumentFilters,
  PurchasingDocumentListResponse,
  PurchasingDocumentPayload,
  PurchasingDocumentSummary,
} from "./types";

export const purchasingDocumentApi = {
  list: (filters: PurchasingDocumentFilters) =>
    api.get<PurchasingDocumentListResponse>("/purchasing-documents", {
      params: filters,
    }),
  detail: (id: number) =>
    api.get<PurchasingDocument>(`/purchasing-documents/${id}`),
  summary: (filters: Omit<PurchasingDocumentFilters, "page" | "page_size">) =>
    api.get<PurchasingDocumentSummary>("/purchasing-documents/summary", {
      params: filters,
    }),
  create: (payload: PurchasingDocumentPayload) =>
    api.post<PurchasingDocument>("/purchasing-documents", payload),
  update: (id: number, payload: Partial<PurchasingDocumentPayload>) =>
    api.patch<PurchasingDocument>(`/purchasing-documents/${id}`, payload),
  archive: (id: number) =>
    api.patch<PurchasingDocument>(`/purchasing-documents/${id}/archive`),
  restore: (id: number) =>
    api.patch<PurchasingDocument>(`/purchasing-documents/${id}/restore`),
};
