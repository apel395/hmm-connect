import api from "@/api/client";

export type PurchasingSummaryParams = {
  date_from?: string;
  date_to?: string;
};

export const purchasingReportsApi = {
  summary: (params: PurchasingSummaryParams = {}) => api.get("/purchasing/summary", { params }),
};