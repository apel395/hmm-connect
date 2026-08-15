import api from "@/api/client";
import type { InventoryMovementFilters } from "./movement";

export const inventoryMovementApi={
  list:(params:InventoryMovementFilters={})=>api.get("/inventory/movements",{params}),
};
