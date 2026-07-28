import api from "@/api/client";

import type {
  SupplierProductPayload,
} from "../typesSupplierProduct";

export const supplierProductApi = {
  list: (supplierId: number) =>
    api.get(
      `/suppliers/${supplierId}/products`
    ),

  create: (
    supplierId: number,
    payload: SupplierProductPayload
  ) =>
    api.post(
      `/suppliers/${supplierId}/products`,
      payload
    ),

  update: (
    supplierId: number,
    id: number,
    payload: SupplierProductPayload
  ) =>
    api.put(
      `/suppliers/${supplierId}/products/${id}`,
      payload
    ),

  remove: (
    supplierId: number,
    id: number
  ) =>
    api.delete(
      `/suppliers/${supplierId}/products/${id}`
    ),
};

export default supplierProductApi;
export type {
  SupplierProductPayload,
};