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
    const response = await api.get<Supplier[]>("/suppliers/lookup", { params: { search, limit } });
    return response.data;
  },

  async detail(id: number): Promise<Supplier> {
    const response = await api.get<Supplier>(`/suppliers/${id}`);
    return response.data;
  },

  create: (payload: SupplierPayload) => api.post<Supplier>("/suppliers", payload),
  update: (id: number, payload: SupplierPayload) => api.put<Supplier>(`/suppliers/${id}`, payload),
  remove: (id: number) => api.delete(`/suppliers/${id}`),
};

export default supplierApi;
