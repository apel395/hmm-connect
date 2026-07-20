import api from "../../api/client";

export interface Warehouse {
  id: number;
  code: string;
  name: string;
  address: string | null;
  is_active: boolean;
}

export interface CreateWarehouseData {
  code: string;
  name: string;
  address?: string;
}

export async function getWarehouses(): Promise<Warehouse[]> {
  const response = await api.get<Warehouse[]>("/warehouses");
  return response.data;
}

export async function createWarehouse(data: CreateWarehouseData): Promise<Warehouse> {
  const response = await api.post<Warehouse>("/warehouses", data);
  return response.data;
}
