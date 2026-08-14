export interface GoodsReceiptItemPayload {
  purchase_order_item_id?: number | null;
  product_id?: number | null;
  quantity: number;
  unit_cost?: number | null;
}

export interface GoodsReceiptCreatePayload {
  purchase_order_id?: number | null;
  supplier_id?: number | null;
  business_unit_id?: number | null;
  department_id?: number | null;
  location_id?: number | null;
  destination_type: "WAREHOUSE" | "DIRECT_USE";
  warehouse_id?: number | null;
  items: GoodsReceiptItemPayload[];
  notes?: string | null;
  received_at?: string;
  external_reference?: string | null;
  cost_correction_reason?: string | null;
}

export interface GoodsReceiptCostCorrectionPayload {
  reason: string;
  items: Array<{ item_id: number; unit_cost: number }>;
}

export interface GoodsReceiptItem {
  id: number;
  purchase_order_item_id?: number | null;
  product_id: number;
  product_code: string;
  product_name: string;
  uom?: string | null;
  quantity: number;
  unit_cost: number;
  line_subtotal?: number;
  is_taxable: boolean;
  tax_rate: number;
  tax_amount: number;
  line_total?: number;
}

export interface GoodsReceipt {
  id: number;
  receipt_number: string;
  status: "DRAFT" | "POSTED" | "RETURNED";
  approval_status?: string | null;
  approval_current_step?: number | null;
  source_mode?: "PO" | "DIRECT";
  purchase_order_id?: number | null;
  purchase_order_number?: string | null;
  supplier_id?: number;
  supplier_name?: string | null;
  received_by_id: number;
  received_by_name?: string | null;
  received_at: string;
  destination_type: string;
  business_unit_id?: number | null;
  business_unit_name?: string | null;
  department_id?: number | null;
  department_name?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  warehouse_id?: number | null;
  warehouse_name?: string | null;
  notes?: string | null;
  delivery_note_number?: string | null;
  subtotal: number;
  tax_amount: number;
  total_amount: number;
  total_value?: number;
  items: GoodsReceiptItem[];
  allowed_actions?: {
    can_edit: boolean; can_submit?: boolean; can_approve?: boolean; can_reject?: boolean; can_post: boolean; can_return?: boolean; can_correct_cost?: boolean; can_print: boolean; can_view_history: boolean; can_manage_attachments: boolean;
  };
  approval_history?: Array<{ level:number; name:string; approver_role:string; location_name?:string|null; status:string; approver_name?:string|null; decided_at?:string|null; comment?:string|null }>;
  activity_history?: import("../components/DocumentActivity").DocumentActivityItem[];
}
