import api from "@/api/client";

export type InventoryListParams = {
  page?: number;
  page_size?: number;
  search?: string;
  warehouse_id?: number;
  account_id?: number;
  location_id?: number;
  business_unit_id?:number;
  as_of?: string;
  show_empty?: boolean;
  health?: "HEALTHY" | "LOW_STOCK";
  movement_class?: "FAST" | "SLOW" | "DEAD";
};

export const inventoryApi = {
  list: (params: InventoryListParams = {}) => api.get("/inventory", { params }),
  detail: (id: number) => api.get(`/inventory/${id}`),
  accounts: async () => (await api.get<{ id: number; account_number: string; account_name: string }[]>("/inventory/accounts")).data,
};
