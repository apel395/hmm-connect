export interface Warehouse {
  id: number;

  code: string;

  name: string;

  address?: string | null;

  is_active: boolean;
}

export interface WarehousePayload {
  code: string;

  name: string;

  address?: string | null;
}
