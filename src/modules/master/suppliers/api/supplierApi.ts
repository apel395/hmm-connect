import api from "@/api/client";
import type { Supplier, SupplierPayload } from "../types";

export type SupplierListParams = {
  page?: number;
  page_size?: number;
  search?: string;
  is_active?: boolean;
};

export type SupplierPageResponse = {
  items: Supplier[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export const supplierApi = {
  async list(params: SupplierListParams = {}): Promise<SupplierPageResponse> {
    const response = await api.get<SupplierPageResponse>("/suppliers", { params });
    return response.data;
  },

  async lookup(search = "", limit = 100): Promise<Supplier[]> {
    // Local searchable dropdowns need the complete active list, not a first-page sample.
    if (!search.trim()) {
      const rows: Supplier[] = [];
      let page = 1;
      while (true) {
        const response = await api.get<SupplierPageResponse>("/suppliers", { params: { page, page_size: 100, is_active: true } });
        rows.push(...response.data.items);
        if (!response.data.has_next) return [...new Map(rows.map(row => [row.id, row])).values()];
        if (!response.data.items.length) throw new Error("Supplier pagination returned an empty incomplete page");
        page += 1;
      }
    }
    const response = await api.get<Supplier[]>("/suppliers/lookup", { params: { search, limit } });
    return response.data;
  },

  async detail(id: number): Promise<Supplier> {
    const response = await api.get<Supplier>(`/suppliers/${id}`);
    return response.data;
  },

  create: (payload: SupplierPayload) => api.post<Supplier>("/suppliers", payload),
  update: (id: number, payload: SupplierPayload) => api.patch<Supplier>(`/suppliers/${id}`, payload),
  remove: (id: number) => api.delete(`/suppliers/${id}`),
};

export default supplierApi;
