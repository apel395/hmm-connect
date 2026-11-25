import api from "@/api/client";
import type { BillingDetails, CateringProfile, CateringSettings, ServiceDetails } from "./cateringTypes";
import type {
  PosBillingOptions,
  PosCateringValidation,
  PosCustomer,
  PosMetadata,
  PosOptions,
  PosPage,
  PosPrintSale,
  PosProduct,
  PosRevenueAccount,
  PosSale,
  PosSalesPage,
  PosStatus,
} from "./types";

export type PosPaymentMethod = "CASH" | "CARD" | "BANK_TRANSFER";
export type PosTransactionType = "POS" | "INVOICE";
export type PosStatusFilter = PosStatus | "ALL";

export type PosListParams = {
  page?: number;
  page_size?: number;
  status?: PosStatusFilter;
  warehouse_id?: number;
  location_id?: number;
  department_id?: number;
  date_from?: string;
  date_to?: string;
  search?: string;
};

export type PosProductParams = PosListParams & {
  group_name?: string;
  transaction_type?: PosTransactionType;
};

export type PosItemIn = ServiceDetails & {
  product_id: number;
  quantity: number;
  unit_price?: number | null;
};

export type PosCreatePayload = {
  guest_count?: number | null;
  discount_preset_id?: string | null;
  checkout_version?: string;
  billing_details?: BillingDetails;
  pos_table_id?: number;
  cashier_session_id?: number;
  event_name?: string;
  order_request_key?: string;
  invoice_due_date?: string;
  receivable_account_id?: number;
  revenue_account_id?: number;
  warehouse_id?: number;
  transaction_type?: PosTransactionType;
  table_number?: string | null;
  queue_number?: string | null;
  sale_date?: string | null;
  customer_id?: number | null;
  business_unit_id?: number | null;
  location_id?: number | null;
  department_id?: number | null;
  notes?: string | null;
  items: PosItemIn[];
};

export type PosUpdatePayload = {
  guest_count?: number | null;
  discount_preset_id?: string | null;
  checkout_version?: string;
  billing_details?: BillingDetails;
  location_id?: number;
  department_id?: number | null;
  invoice_due_date?: string;
  receivable_account_id?: number;
  revenue_account_id?: number;
  transaction_type?: PosTransactionType;
  table_number?: string | null;
  queue_number?: string | null;
  sale_date?: string | null;
  customer_id?: number | null;
  notes?: string | null;
  items: PosItemIn[];
};

export type PosMetadataPayload = {
  transaction_type: PosTransactionType;
  table_number?: string | null;
  queue_number?: string | null;
};

export type PosPostPayload = {
  discount_preset_id?: string | null;
  checkout_version?: string;
  invoice_due_date?: string;
  receivable_account_id?: number;
  customer_id?: number;
  revenue_account_id?: number;
  payment_method: PosPaymentMethod;
  payment_received?: number | null;
  discount_amount?: number | null;
};

export type PosVoidPayload = {
  reason?: string | null;
};

export const posApi = {
  cateringSettings: (id:number) => api.get<CateringProfile>(`/pos/catering-locations/${id}`),
  saveCateringSettings: (id:number,payload:CateringSettings) => api.put<CateringProfile>(`/pos/catering-locations/${id}`,payload),
  validateCateringLocation: (id:number,payload:{department_id?:number;items:PosItemIn[]}) => api.post<PosCateringValidation>(`/pos/catering-locations/${id}/validate-order`,payload),
  billingOptions: () => api.get<PosBillingOptions>("/pos/billing-options"),
  createCustomer: (payload: { customer_name: string; phone?: string; email?: string; address?: string }) => api.post<PosCustomer>("/pos/customers", payload),
  correctToAR: (id: number, payload: { customer_id: number; invoice_due_date: string; receivable_account_id?: number; correction_date: string; confirm_unpaid: true }) => api.post<PosSale>(`/pos/${id}/correct-to-ar`, payload),
  options: () => api.get<PosOptions>("/pos/options"),
  revenueAccounts: (location_id?: number) => api.get<PosRevenueAccount[]>("/pos/revenue-accounts", { params: { location_id } }),
  products: (params: PosProductParams = {}) => api.get<PosPage<PosProduct>>("/pos/products", { params }),
  list: (params: PosListParams = {}) => api.get<PosSalesPage>("/pos", { params }),
  detail: (id: number) => api.get<PosSale>(`/pos/${id}`),
  create: (payload: PosCreatePayload) => api.post<PosSale>("/pos", payload),
  update: (id: number, payload: PosUpdatePayload) => api.put<PosSale>(`/pos/${id}`, payload),
  metadata: (id: number, payload: PosMetadataPayload) => api.patch<PosMetadata>(`/pos-metadata/${id}`, payload),
  post: (id: number, payload: PosPostPayload) => api.post<PosSale>(`/pos/${id}/post`, payload),
  void: (id: number, payload: PosVoidPayload = {}) => api.post<PosSale>(`/pos/${id}/void`, payload),
  print: (id: number) => api.get<PosPrintSale>(`/pos/${id}/print`),
};

