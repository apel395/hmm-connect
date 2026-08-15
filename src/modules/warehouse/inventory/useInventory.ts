import { useQuery } from "@tanstack/react-query";
import { inventoryApi, type InventoryListParams } from "./api";

export function useInventory(params: InventoryListParams = {}) {
  return useQuery({
    queryKey: ["inventory", params],
    queryFn: async () => (await inventoryApi.list(params)).data,
  });
}
