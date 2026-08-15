import { useQuery } from "@tanstack/react-query";
import { inventoryMovementApi } from "./movementApi";
import type { InventoryMovementFilters, InventoryMovementPage } from "./movement";

export function useInventoryMovements(filters:InventoryMovementFilters={}){
  return useQuery({queryKey:["inventory-movements",filters],queryFn:async()=>((await inventoryMovementApi.list(filters)).data as InventoryMovementPage)});
}
