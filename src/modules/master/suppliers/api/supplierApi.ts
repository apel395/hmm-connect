import api from "@/api/client";

export interface SupplierPICPayload {
  id?: number;

  pic_name: string;

  phone?: string | null;

  unit?: string | null;

  item?: string | null;
}

export interface SupplierPayload {
  code: string;

  name: string;

  address: string;

  bank_name: string;

  bank_account_number: string;

  bank_account_name: string;

  is_active?: boolean;

  rows: SupplierPICPayload[];
}

export const supplierApi = {
  list: () =>
    api.get("/suppliers"),

  detail: (id: number) =>
    api.get(`/suppliers/${id}`),

  create: (
    payload: SupplierPayload
  ) =>
    api.post(
      "/suppliers",
      payload
    ),

  update: (
    id: number,
    payload: SupplierPayload
  ) =>
    api.put(
      `/suppliers/${id}`,
      payload
    ),

  remove: (id: number) =>
    api.delete(
      `/suppliers/${id}`
    ),
};

export default supplierApi;