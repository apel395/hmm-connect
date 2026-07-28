import api from "@/api/client";

import type {
  WarehousePayload,
} from "../types";

export const warehouseApi = {

  list: () =>
    api.get("/warehouses"),

  create: (
    payload: WarehousePayload
  ) =>
    api.post(
      "/warehouses",
      payload
    ),

};

export default warehouseApi;
