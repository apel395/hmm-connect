export interface InventoryMovement {
  id:number; movement_number:string; movement_date:string; movement_type:string;
  inventory_account_id?:number|null; inventory_account_code?:string|null; inventory_account_name?:string|null;
  product_id:number; product_code:string; product_name:string;
  warehouse_id:number; warehouse_name:string; quantity:number; unit_cost:number; movement_value:number;
  reference_type?:string|null; reference_id?:number|null; reference_number?:string|null;
  goods_receipt_id?:number|null; goods_receipt_item_id?:number|null; receipt_number?:string|null;
  purchase_order_id?:number|null; purchase_order_item_id?:number|null; purchase_order_number?:string|null;
  business_unit_id?:number|null; location_id?:number|null; department_id?:number|null; notes?:string|null;
}

export interface InventoryMovementFilters {
  product_id?:number; warehouse_id?:number; purchase_order_id?:number; goods_receipt_id?:number; location_id?:number; department_id?:number;
  account_id?:number; date_from?:string; date_to?:string;
  page?:number; page_size?:number; search?:string;
}

export interface InventoryMovementPage {
  items: InventoryMovement[];
  summary?:{in_qty:number;out_qty:number;net_qty:number;in_value:number;out_value:number;net_value:number};
  totals_by_account?:Array<{account_id:number|null;account_code:string|null;account_name:string|null;in_qty:number;out_qty:number;net_qty:number;in_value:number;out_value:number;net_value:number}>;
  page:number; page_size:number; total_items:number; total_pages:number; has_next:boolean; has_previous:boolean;
}
