export type StockOpnameItem = {
  id: number;
  product_id: number;
  product_code: string;
  product_name: string;
  uom: string;
  system_quantity: number;
  physical_quantity: number | null;
  variance_quantity: number | null;
  unit_cost: number;
  variance_value: number;
};

export type StockOpname = {
  id: number;
  opname_number: string;
  status: string;
  count_date: string;
  warehouse_id: number;
  warehouse_name?: string;
  location_name?: string;
  department_name?: string;
  notes?: string;
  total_items: number;
  total_variance_quantity: number;
  items: StockOpnameItem[];
  allowed_actions?: {
    can_edit?: boolean;
    can_submit?: boolean;
    can_approve?: boolean;
    can_reject?: boolean;
    can_post?: boolean;
  };
};

export type StockOpnameList = {
  items: StockOpname[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};
