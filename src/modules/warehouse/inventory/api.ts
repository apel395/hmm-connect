import api from "@/api/client";

export type InventoryListParams = {
  page?: number;
  page_size?: number;
  search?: string;
  warehouse_id?: number;
  health?: "HEALTHY" | "LOW_STOCK";
};

export const inventoryApi = {
  list: (params: InventoryListParams = {}) => api.get("/inventory", { params }),
  detail: (id: number) => api.get(`/inventory/${id}`),
};
