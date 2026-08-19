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
  market_only?: boolean;
  exclude_market?: boolean;
};

export type ProductClassificationGroup = {
  id: number;
  code: string;
  name: string;
  subgroups: Array<{ id: number; code: string; name: string }>;
};

export const productApi = {
  list: (params: ProductListParams = {}) =>
    api.get("/products", { params }),

  classificationMaster: () =>
    api.get<ProductClassificationGroup[]>("/products/classification-master"),

  lookup: (search = "", limit = 30, marketOnly = false, excludeMarket = false) =>
    api.get("/products/lookup", { params: { search, limit, market_only: marketOnly, exclude_market: excludeMarket } }),

  detail: (id: number) =>
    api.get(`/products/${id}`),

  create: (payload: ProductCreateRequest) =>
    api.post("/products", payload),

  update: (id: number, payload: ProductUpdateRequest) =>
    api.patch(`/products/${id}`, payload),

  remove: (id: number) =>
    api.delete(`/products/${id}`),
};

export default productApi;
