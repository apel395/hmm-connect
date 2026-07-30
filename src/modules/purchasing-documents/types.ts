export type PurchasingDocumentType =
  | "PURCHASE_REQUISITION"
  | "PURCHASE_ORDER";

export type PurchasingDocumentSource =
  | "LIVE"
  | "HISTORICAL_IMPORT"
  | "OPENING_BALANCE";

export type CashflowStage = "PLANNED" | "COMMITTED" | "PAYABLE" | "PAID";

export interface PurchasingDocument {
  id: number;
  document_type: PurchasingDocumentType;
  document_number: string;
  document_date: string;
  status: string;
  source_type: string;
  supplier_id: number | null;
  supplier_name: string | null;
  department_id: number | null;
  department_name: string | null;
  location_id: number | null;
  location_name: string | null;
  responsible_user_id: number | null;
  responsible_user_name: string | null;
  currency: string | null;
  subtotal: string | null;
  tax_amount: string | null;
  total_amount: string | null;
  cashflow_stage: CashflowStage;
  expected_payment_date: string | null;
  external_reference: string | null;
  notes: string | null;
  is_active: boolean;
  created_by: number | null;
  created_at: string;
  updated_at: string;
  attachment_count: number;
  related_document_count: number;
}

export interface PurchasingDocumentPayload {
  document_type: PurchasingDocumentType;
  document_number: string;
  document_date: string;
  status: string;
  source_type: PurchasingDocumentSource;
  supplier_id: number | null;
  currency: string | null;
  subtotal: string | null;
  tax_amount: string | null;
  total_amount: string | null;
  cashflow_stage: "PLANNED" | "COMMITTED";
  expected_payment_date: string | null;
  external_reference: string | null;
  notes: string | null;
}

export interface PurchasingDocumentListResponse {
  items: PurchasingDocument[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

export interface PurchasingDocumentSummary {
  planned_amount: string;
  committed_amount: string;
  expected_this_month: string;
  missing_supplier_count: number;
  missing_amount_count: number;
  missing_attachment_count: number;
  purchase_requisition_count: number;
  purchase_order_count: number;
}

export interface PurchasingDocumentFilters {
  page: number;
  page_size: number;
  search?: string;
  document_type?: string;
  status?: string;
  source_type?: string;
  supplier_id?: number;
  cashflow_stage?: string;
  document_date_from?: string;
  document_date_to?: string;
  expected_payment_date_from?: string;
  expected_payment_date_to?: string;
  is_active?: boolean;
}
