export interface Inventory {
  id: number;
  product_id: number;
  product_code: string;
  product_name: string;
  uom: string;
  warehouse_id: number;
  warehouse_code: string;
  warehouse_name: string;
  quantity: number;
  average_cost: number;
  stock_value: number;
  minimum_stock: number;
  low_stock: boolean;
  shortage: number;
  below_minimum?: boolean;
  needs_reorder?: boolean;
  movement_class?: "FAST" | "SLOW" | "DEAD" | "EMPTY";
  oldest_stock_date?: string | null;
  stock_age_days?: number | null;
  aging_quantities?: { FAST: number; SLOW: number; DEAD: number };
  last_out?: string | null;
  last_movement?: string | null;
}
