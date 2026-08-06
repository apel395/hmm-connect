export interface GoodsReceiptItemPayload {
  purchase_order_item_id: number;

  quantity: number;
}


export interface GoodsReceiptCreatePayload {
  destination_type: "WAREHOUSE" | "DIRECT_USE";

  warehouse_id?: number | null;

  items: GoodsReceiptItemPayload[];

  notes?: string | null;

  received_at?: string;

  external_reference?: string | null;
}


export interface GoodsReceiptItem {
  id: number;

  purchase_order_item_id: number;

  product_id: number;

  product_code: string;

  product_name: string;

  uom?: string | null;

  quantity: number;

  unit_cost: number;
}


export interface GoodsReceipt {
  id: number;

  receipt_number: string;

  status: "DRAFT" | "POSTED";

  purchase_order_id: number;

  purchase_order_number: string;

  supplier_id?: number;

  supplier_name?: string | null;

  received_by_id: number;

  received_by_name?: string | null;

  received_at: string;

  destination_type: string;

  warehouse_id?: number | null;

  warehouse_name?: string | null;

  notes?: string | null;

  delivery_note_number?: string | null;

  items: GoodsReceiptItem[];

  allowed_actions?: {
    can_edit: boolean; can_post: boolean; can_print: boolean; can_view_history: boolean; can_manage_attachments: boolean;
  };
  activity_history?: import("../components/DocumentActivity").DocumentActivityItem[];
}
