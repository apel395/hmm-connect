import api from "@/api/client";
import type { WarehousePayload, WarehouseUpdatePayload } from "../types";

export const warehouseApi = {
  list: () => api.get("/warehouses", { params: { active_only: false } }),
  create: (payload: WarehousePayload) => api.post("/warehouses", payload),
  update: (id: number, payload: WarehouseUpdatePayload) => api.patch(`/warehouses/${id}`, payload),
};

export default warehouseApi;
