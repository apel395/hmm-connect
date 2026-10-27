import api from "@/api/client";

export type Payment = {
  id: number;
  payment_number: string;
  supplier_id: number;
  supplier_name: string;
  payment_date: string;
  payment_method: string;
  currency: string;
  total_amount: number;
  bank_charge_amount?: number;
  short_over_amount?: number;
  bank_charge_account_id?: number | null;
  short_over_account_id?: number | null;
  difference_reason?: string | null;
  expected_funding?: number;
  allocated_amount: number;
  funded_amount: number;
  reference_number?: string | null;
  cheque_number?: string | null;
  status: string;
  notes?: string | null;
  source_type?: string | null;
  journal_entry_id?: number | null;
  journal_number?: string | null;
  business_unit_id?: number | null;
  location_id?: number | null;
  department_id?: number | null;
  allocations: any[];
  funding_lines: any[];
  allowed_actions?: Record<string, boolean>;
  activity_history?: any[];
  allocation_exception_rows?: any[];
};

export type EligiblePaymentSupplier = {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
};

export const listPayments = async (params: any = {}) => (await api.get("/payments", { params })).data;
export type ReadyToPayInvoice = {
  id: number;
  invoice_number: string;
  supplier_invoice_number: string;
  supplier_id: number;
  supplier_name: string | null;
  invoice_date: string;
  due_date: string | null;
  currency: string;
  total_amount: number;
  outstanding_balance: number;
  reserved_amount: number;
  available_balance: number;
};
export type ReadyToPayPage = {
  items: ReadyToPayInvoice[];
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
  totals_by_currency: Record<string, number>;
};
export const listReadyToPay = async (params: {page?: number; page_size?: number; search?: string; currency?: string} = {}) =>
  (await api.get<ReadyToPayPage>("/payments/ready-to-pay", {params})).data;
export const getPayment = async (id: number) => (await api.get<Payment>(`/payments/${id}`)).data;
export const eligibleSuppliers = async (currency = "IDR", include_supplier_id?: number) =>
  (await api.get<EligiblePaymentSupplier[]>("/payments/eligible-suppliers", {
    params: { currency, include_supplier_id: include_supplier_id || undefined },
  })).data;
export const eligibleInvoices = async (supplier_id: number, currency = "IDR") => (await api.get("/payments/eligible-invoices", { params: { supplier_id, currency } })).data;
export const eligibleVouchers = async (supplier_id: number, currency = "IDR") => (await api.get("/payments/eligible-vouchers", { params: { supplier_id, currency } })).data;
export const createPayment = async (payload: any) => (await api.post<Payment>("/payments", payload)).data;
export const updatePayment = async (id: number, payload: any) => (await api.patch<Payment>(`/payments/${id}`, payload)).data;
export const paymentAction = async (id: number, action: string) => (await api.post<Payment>(`/payments/${id}/${action}`)).data;
export const adminUnpostPayment = async (id: number) => (await api.post(`/payments/${id}/unpost`)).data;
export const adminCancelPostedPayment = async (id: number) => (await api.post(`/payments/${id}/cancel-posted`)).data;
export const adminReopenPayment = async (id: number) => (await api.post(`/payments/${id}/reopen`)).data;
