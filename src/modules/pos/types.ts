/**
 * Frontend contracts for POS API responses.
 *
 * These describe backend payloads only. Permission, pricing, posting, and
 * database routing rules stay in the backend.
 */

export type PosPage<T> = {
  items: T[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type PosStatus = "DRAFT" | "POSTED" | "VOID";
export type PosAmount = number | string;
export type PosChoice = { id: number; code: string; name: string; address?: string };

export type PosLocation = {
  id: number;
  name: string;
  business_unit_id?: number | null;
  catalog_type: "HOTEL" | "CATERING" | string;
  has_outlets?: boolean;
};

export type PosDepartment = {
  id: number;
  name: string;
  display_name?: string;
  location_id: number;
  code?: string;
  is_outlet?: boolean;
  is_fnb_outlet?: boolean;
  parent_department_id?: number | null;
  parent_department_name?: string | null;
};

export type PosOptions = { locations: PosLocation[]; departments: PosDepartment[] };

export type PosProduct = {
  product_id: number;
  product_code: string;
  product_name: string;
  group_name?: string | null;
  uom?: string | null;
  selling_price: PosAmount;
  service_charge_rate: PosAmount;
  tax_rate: PosAmount;
  tax_type?: string;
  is_taxable: boolean;
  sale_available: boolean;
  unavailable_reason?: string | null;
  catalog_type: "HOTEL" | "CATERING" | string;
  catering_shared?: boolean;
  sales_location_id?: number;
  sales_business_unit_id?: number;
  department_id?: number;
  description?: string | null;
  registration_number?: string | null;
  service_period_from?: string | null;
  service_period_to?: string | null;
};

export type PosSaleItem = {
  id?: number;
  product_id: number;
  product_code?: string | null;
  product_name?: string | null;
  description?: string | null;
  registration_number?: string | null;
  service_period_from?: string | null;
  service_period_to?: string | null;
  uom?: string | null;
  line_number?: number | null;
  quantity: PosAmount;
  unit_price: PosAmount;
  tax_type?: string;
  tax_rate: PosAmount;
  tax_amount: PosAmount;
  service_charge_rate?: PosAmount;
  service_charge_amount?: PosAmount;
  line_amount: PosAmount;
  unit_cost?: PosAmount;
};

/** Shared serialized shape returned by list, detail, create, update, post and void. */
export type PosSale = {
  id: number;
  transaction_number: string;
  status: PosStatus;
  transaction_type: "POS" | "INVOICE";
  sale_date?: string | null;
  guest_count?: number | null;
  pos_table_id?: number | null;
  cashier_session_id?: number | null;
  order_mode?: string | null;
  event_name?: string | null;
  order_request_key?: string | null;
  warehouse_id?: number | null;
  warehouse_code?: string | null;
  warehouse_name?: string | null;
  customer_id?: number | null;
  customer_code?: string | null;
  customer_name?: string | null;
  business_unit_id?: number | null;
  location_id?: number | null;
  location_name?: string | null;
  department_id?: number | null;
  department_name?: string | null;
  revenue_account_id?: number | null;
  invoice_due_date?: string | null;
  receivable_account_id?: number | null;
  ar_correction_journal_id?: number | null;
  account_receivable_id?: number | null;
  outstanding_amount?: PosAmount | null;
  payment_status?: string | null;
  payment_method?: string | null;
  payment_received?: PosAmount | null;
  change_amount?: PosAmount | null;
  discount_amount?: PosAmount;
  subtotal?: PosAmount;
  service_charge_amount?: PosAmount;
  tax_amount?: PosAmount;
  total_amount?: PosAmount;
  checkout_snapshot?: Record<string, unknown> | null;
  billing_details?: Record<string, unknown> | null;
  notes?: string | null;
  created_by_id?: number | null;
  created_by_name?: string | null;
  posted_by_id?: number | null;
  posted_by_name?: string | null;
  posted_at?: string | null;
  void_reason?: string | null;
  journal_number?: string | null;
  table_number?: string | null;
  queue_number?: string | null;
  items: PosSaleItem[];
};

export type PosSaleSummary = {
  status_counts: Partial<Record<PosStatus, number>>;
  posted_count: number;
  posted_value: PosAmount;
  tax_value: PosAmount;
};

export type PosSalesPage = PosPage<PosSale> & { summary: PosSaleSummary };

export type PosBillingOptions = {
  customers: PosChoice[];
  receivable_accounts: PosChoice[];
  default_receivable_account_id?: number | null;
};

export type PosRevenueAccount = { id: number; code?: string; name: string };
export type PosCustomer = { id: number; code: string; name: string };
export type PosMetadata = {
  id: number;
  transaction_number: string;
  transaction_type: "POS" | "INVOICE";
  table_number?: string | null;
  queue_number?: string | null;
};
export type PosCateringValidation = { location_id: number; business_unit_id?: number | null; department_id?: number | null };
export type PosPrintSale = PosSale & {
  printed_by: string;
  generated_at: string;
  client_invoice?: unknown | null;
};

/** Draft line edits submitted from the sales/document detail dialog. */
export type PosDraftLine = {
  product_id: number;
  quantity: number;
  unit_price: number;
  description?: string;
  uom?: string;
  registration_number?: string;
  service_period_from?: string | null;
  service_period_to?: string | null;
};
