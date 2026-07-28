export interface GoodsReceiptItemPayload {
  purchase_order_item_id: number;

  quantity: number;
}


export interface GoodsReceiptCreatePayload {
  destination_type: string;

  warehouse_id?: number | null;

  items: GoodsReceiptItemPayload[];

  notes?: string | null;
}


export interface GoodsReceiptItem {
  id: number;

  purchase_order_item_id: number;

  product_id: number;

  quantity: number;

  unit_cost: number;
}


export interface GoodsReceipt {
  id: number;

  receipt_number: string;

  purchase_order_id: number;

  received_by_id: number;

  received_at: string;

  destination_type: string;

  warehouse_id?: number | null;

  notes?: string | null;

  items: GoodsReceiptItem[];
}
