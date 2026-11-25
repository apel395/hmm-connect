import api from "@/api/client";
import type {
  StockOpname,
  StockOpnameCountItem,
  StockOpnameCreatePayload,
  StockOpnameList,
  StockOpnameListParams,
} from "./types";

export const stockOpnameApi = {
  list: (params: StockOpnameListParams = {}) =>
    api.get<StockOpnameList>("/stock-opnames", { params }),
  detail: (id: number) => api.get<StockOpname>(`/stock-opnames/${id}`),
  create: (payload: StockOpnameCreatePayload) =>
    api.post<StockOpname>("/stock-opnames", payload),
  count: (id: number, items: StockOpnameCountItem[], notes?: string) =>
    api.patch<StockOpname>(`/stock-opnames/${id}/count`, { items, notes }),
  submit: (id: number) => api.post<StockOpname>(`/stock-opnames/${id}/submit`),
  approve: (id: number, comment?: string) =>
    api.post<StockOpname>(`/stock-opnames/${id}/approve`, { comment }),
  reject: (id: number, comment: string) =>
    api.post<StockOpname>(`/stock-opnames/${id}/reject`, { comment }),
  post: (id: number) => api.post<StockOpname>(`/stock-opnames/${id}/post`),
  unpost: (id: number) => api.post<StockOpname>(`/stock-opnames/${id}/unpost`),
  void: (id: number, reason: string) =>
    api.post<StockOpname>(`/stock-opnames/${id}/void`, { reason }),
};
