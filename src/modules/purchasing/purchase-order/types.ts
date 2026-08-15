export interface PurchaseOrderItem {
  id: number;
  purchase_order_id?: number;
  purchase_requisition_item_id?: number | null;
  product_id: number;
  product_code?: string;
  product_name: string;
  description?: string | null;
  uom?: string;
  quantity: number;
  received_quantity: number;
  remaining_quantity?: number;
  unit_price: number;
  total_price: number;
  is_taxable: boolean;
  tax_rate: number;
  tax_amount: number;
  line_total?: number;
}

export interface PurchaseOrder {
  id: number;
  po_number: string;
  supplier_id: number;
  supplier_name: string;
  business_unit_id?: number | null;
  business_unit_name?: string | null;
  department_id?: number | null;
  department_name?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  purchase_requisition_id?: number | null;
  purchase_requisition_ids?: number[];
  source_pr_id?: number | null;
  source_pr_number?: string | null;
  source_purchase_requisitions?: Array<{ id: number; pr_number: string }>;
  approval_status?: string | null;
  current_approver_role?: string | null;
  status: "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "PARTIALLY_RECEIVED" | "RECEIVED" | "REJECTED";
  order_date: string;
  expected_date?: string | null;
  expiry_date?: string | null;
  notes?: string | null;
  subtotal: number;
  discount_amount: number;
  tax_amount: number;
  total_amount: number;
  items: PurchaseOrderItem[];
  creation_type?: "FROM_PR" | "DIRECT";
  allowed_actions?: DocumentAllowedActions;
  approval_history?: ApprovalHistoryItem[];
  activity_history?: import("../components/DocumentActivity").DocumentActivityItem[];
}

export interface PurchaseOrderPage {
  items: PurchaseOrder[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
}

export interface DocumentAllowedActions {
  can_edit: boolean; can_submit: boolean; can_approve: boolean; can_reject: boolean;
  can_print: boolean; can_view_history: boolean; can_manage_attachments: boolean; can_receive?: boolean;
}

export interface ApprovalHistoryItem {
  level: number; name: string; approver_role: string; location_name?: string | null; status: string;
  approver_name?: string | null; decided_at?: string | null; comment?: string | null;
}
