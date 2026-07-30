import api from "@/api/client";
import type { Supplier, SupplierPayload } from "../types";

type SupplierListResponse =
  | Supplier[]
  | { items: Supplier[] }
  | { data: Supplier[] };

function normalizeList(response: SupplierListResponse): Supplier[] {
  if (Array.isArray(response)) return response;
  if ("items" in response && Array.isArray(response.items)) return response.items;
  if ("data" in response && Array.isArray(response.data)) return response.data;
  return [];
}

export const supplierApi = {
  async list(): Promise<Supplier[]> {
    const response = await api.get<SupplierListResponse>("/suppliers");
    return normalizeList(response.data);
  },

  async detail(id: number): Promise<Supplier> {
    const response = await api.get<Supplier>(`/suppliers/${id}`);
    return response.data;
  },

  create: (payload: SupplierPayload) =>
    api.post<Supplier>("/suppliers", payload),

  update: (id: number, payload: SupplierPayload) =>
    api.put<Supplier>(`/suppliers/${id}`, payload),

  remove: (id: number) => api.delete(`/suppliers/${id}`),
};

export default supplierApi;
