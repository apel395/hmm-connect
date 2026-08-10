import api from "@/api/client";

export type InvoiceLine = {
  id?: number;
  product_id?: number | null;
  product_code?: string | null;
  product_name?: string | null;
  purchase_order_item_id?: number | null;
  goods_receipt_item_id?: number | null;
  description: string;
  quantity: number;
  uom?: string | null;
  unit_price: number;
  line_amount?: number;
  account_id?: number | null;
  account_code?: string | null;
  account_name?: string | null;
  department_id?: number | null;
  notes?: string | null;
};

export type ThreeWayMatchLine = {
  invoice_line_id?: number | null;
  product_id?: number | null;
  product_code?: string | null;
  product_name?: string | null;
  receipt_item_id?: number | null;
  purchase_order_item_id?: number | null;
  received_quantity: number;
  previously_invoiced_quantity: number;
  available_quantity: number;
  invoice_quantity: number;
  po_unit_price?: number | null;
  receipt_unit_cost?: number | null;
  invoice_unit_price: number;
  price_difference?: number | null;
  uom?: string | null;
  reference_uom?: string | null;
  status: "MATCHED" | "MISMATCH";
  issues: string[];
};

export type ThreeWayMatch = {
  status: "MATCHED" | "MISMATCH" | "NOT_APPLICABLE";
  can_verify: boolean;
  message: string;
  supplier_match: boolean;
  line_count: number;
  matched_lines: number;
  issues: string[];
  lines: ThreeWayMatchLine[];
};

export type SupplierInvoice = {
  id: number;
  internal_invoice_number: string;
  supplier_invoice_number: string;
  supplier_id: number;
  supplier_name: string;
  invoice_date: string;
  received_date?: string | null;
  due_date?: string | null;
  purchase_order_id?: number | null;
  purchase_order_number?: string | null;
  goods_receipt_id?: number | null;
  receipt_number?: string | null;
  business_unit_id?: number | null;
  department_id?: number | null;
  department_name?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  currency: string;
  subtotal: number;
  discount_amount: number;
  tax_amount: number;
  withholding_tax_amount: number;
  total_amount: number;
  paid_amount?: number;
  balance_amount?: number;
  payment_status?: string;
  status: string;
  notes?: string | null;
  source_type: string;
  lines: InvoiceLine[];
  three_way_match?: ThreeWayMatch;
  related_journal?: { id: number; journal_number: string; status: string } | null;
  allowed_actions?: Record<string, boolean>;
  activity_history?: any[];
};

export type InvoicePayload = {
  supplier_invoice_number: string;
  supplier_id: number;
  invoice_date: string;
  received_date?: string | null;
  due_date?: string | null;
  purchase_order_id?: number | null;
  goods_receipt_id?: number | null;
  business_unit_id?: number | null;
  department_id?: number | null;
  location_id?: number | null;
  currency: string;
  discount_amount: number;
  tax_amount: number;
  withholding_tax_amount: number;
  notes?: string | null;
  source_type: string;
  lines: InvoiceLine[];
};

export type EligibleReceiptSource = {
  id: number;
  receipt_number: string;
  purchase_order_id?: number | null;
  supplier_id?: number | null;
  supplier_name?: string | null;
  business_unit_id?: number | null;
  department_id?: number | null;
  location_id?: number | null;
  received_at?: string | null;
};

export const listInvoices = async (params: any = {}) => (await api.get("/supplier-invoices", { params })).data;
export const listEligibleReceiptSources = async () => (await api.get<EligibleReceiptSource[]>("/supplier-invoice-sources/eligible-receipts")).data;
export const getInvoice = async (id: number) => (await api.get<SupplierInvoice>(`/supplier-invoices/${id}`)).data;
export const createInvoice = async (payload: InvoicePayload) => (await api.post<SupplierInvoice>("/supplier-invoices", payload)).data;
export const updateInvoice = async (id: number, payload: InvoicePayload) => (await api.patch<SupplierInvoice>(`/supplier-invoices/${id}`, payload)).data;
export const invoiceAction = async (id: number, action: string) => (await api.post(`/supplier-invoices/${id}/${action}`)).data;
export const adminUnpostInvoice = async (id: number) => (await api.post(`/supplier-invoices/${id}/unpost`)).data;
export const adminReopenInvoice = async (id: number) => (await api.post(`/supplier-invoices/${id}/reopen`)).data;
