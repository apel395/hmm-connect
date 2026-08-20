import api from "@/api/client";
import type { StockOpname, StockOpnameList } from "./types";

export const stockOpnameApi = {
  list: (params: Record<string, unknown> = {}) => api.get<StockOpnameList>("/stock-opnames", { params }),
  detail: (id: number) => api.get<StockOpname>(`/stock-opnames/${id}`),
  create: (payload: { warehouse_id: number; count_date?: string; business_unit_id?: number; location_id?: number; department_id?: number; notes?: string }) => api.post<StockOpname>("/stock-opnames", payload),
  count: (id: number, items: Array<{ item_id: number; physical_quantity: number }>, notes?: string) => api.patch<StockOpname>(`/stock-opnames/${id}/count`, { items, notes }),
  submit: (id: number) => api.post<StockOpname>(`/stock-opnames/${id}/submit`),
  approve: (id: number, comment?: string) => api.post<StockOpname>(`/stock-opnames/${id}/approve`, { comment }),
  reject: (id: number, comment: string) => api.post<StockOpname>(`/stock-opnames/${id}/reject`, { comment }),
  post: (id: number) => api.post<StockOpname>(`/stock-opnames/${id}/post`),
};
