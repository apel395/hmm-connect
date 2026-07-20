import api from "../../api/client";

export interface InventoryItem {
  product_id: number;
  code: string;
  name: string;
  uom: string;
  warehouse_id: number;
  warehouse_code: string;
  warehouse_name: string;
  quantity: number;
  average_cost: number;
}

export async function getInventory(): Promise<InventoryItem[]> {
  const response = await api.get<InventoryItem[]>("/inventory");
  return response.data;
}
