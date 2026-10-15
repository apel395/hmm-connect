import { useQuery } from "@tanstack/react-query";
import { inventoryApi, type InventoryListParams } from "./api";

export function useInventory(
  params: InventoryListParams = {},
  options: { enabled?: boolean } = {},
) {
  return useQuery({
    enabled: options.enabled ?? true,
    queryKey: ["inventory", params],
    queryFn: async () => (await inventoryApi.list(params)).data,
    placeholderData: (previous) => previous,
  });
}
