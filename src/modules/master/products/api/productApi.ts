import api from "@/api/client";

import type {
  ProductCreateRequest,
  ProductUpdateRequest,
} from "../types";

export const productApi = {
  list: () =>
    api.get("/products"),

  detail: (id: number) =>
    api.get(`/products/${id}`),

  create: (
    payload: ProductCreateRequest
  ) =>
    api.post(
      "/products",
      payload
    ),

  update: (
    id: number,
    payload: ProductUpdateRequest
  ) =>
    api.put(
      `/products/${id}`,
      payload
    ),

  remove: (id: number) =>
    api.delete(
      `/products/${id}`
    ),
};

export default productApi;