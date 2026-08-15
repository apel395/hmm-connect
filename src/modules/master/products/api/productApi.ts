import api from "@/api/client";

import type {
  ProductCreateRequest,
  ProductUpdateRequest,
} from "../types";

export type ProductListParams = {
  page?: number;
  page_size?: number;
  search?: string;
  active_only?: boolean;
};

export const productApi = {
  list: (params: ProductListParams = {}) =>
    api.get("/products", { params }),

  lookup: (search = "", limit = 30) =>
    api.get("/products/lookup", { params: { search, limit } }),

  detail: (id: number) =>
    api.get(`/products/${id}`),

  create: (payload: ProductCreateRequest) =>
    api.post("/products", payload),

  update: (id: number, payload: ProductUpdateRequest) =>
    api.put(`/products/${id}`, payload),

  remove: (id: number) =>
    api.delete(`/products/${id}`),
};

export default productApi;