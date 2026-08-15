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
  reorder_level: number;
  maximum_stock: number;
  below_minimum: boolean;
  needs_reorder: boolean;
}
