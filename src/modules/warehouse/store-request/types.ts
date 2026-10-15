export type StoreRequestStatus = "DRAFT" | "PENDING_APPROVAL" | "APPROVED" | "REJECTED" | "PARTIALLY_ISSUED" | "ISSUED";

export interface StoreRequestItem {
  id: number;
  product_id: number;
  product_code: string;
  product_name: string;
  uom: string;
  requested_quantity: number;
  issued_quantity: number;
  remaining_quantity: number;
  available_stock: number;
}

export interface StoreIssueItem {
  id: number;
  store_request_item_id: number;
  product_id: number;
  product_code: string;
  product_name: string;
  quantity: number;
  uom: string;
}

export interface StoreIssue {
  issue_date?: string;
  id: number;
  issue_number: string;
  status: "DRAFT" | "POSTED";
  notes?: string | null;
  created_at: string;
  posted_at?: string | null;
  items: StoreIssueItem[];
}

export interface StoreRequest {
  id: number;
  sr_number: string;
  status: StoreRequestStatus;
  request_date: string;
  last_issue_date?: string | null;
  requester_name?: string | null;
  business_unit_id: number;
  business_unit_name?: string | null;
  department_id: number;
  department_name?: string | null;
  location_id: number;
  location_name?: string | null;
  warehouse_id: number;
  warehouse_code?: string | null;
  warehouse_name?: string | null;
  notes?: string | null;
  total_requested_quantity: number;
  total_issued_quantity: number;
  total_remaining_quantity: number;
  items?: StoreRequestItem[];
  issues?: StoreIssue[];
  allowed_actions?: {
    can_edit?: boolean;
    can_submit?: boolean;
    can_approve?: boolean;
    can_reject?: boolean;
    can_issue?: boolean;
    can_print?: boolean;
  };
  approval_history?: Array<{
    level: number;
    name: string;
    approver_role: string;
    location_name?: string | null;
    status: string;
    approver_name?: string | null;
    decided_at?: string | null;
    comment?: string | null;
  }>;
}

export interface StoreRequestPayload {
  request_date?: string;
  business_unit_id?: number;
  department_id?: number;
  location_id?: number;
  warehouse_id: number;
  notes?: string | null;
  items: Array<{ product_id: number; quantity: number }>;
}

export interface StoreIssuePayload {
  issue_date?: string;
  notes?: string | null;
  items: Array<{ item_id: number; quantity: number }>;
}
