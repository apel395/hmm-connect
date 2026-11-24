import api from "@/api/client";
import type {
  FinanceActivityEvent,
  FinanceAllowedActions,
  FinancePage,
  FinancePageParams,
  RawPaymentStatus,
} from "@/modules/finance/types";

export type PaymentStatus = "DRAFT" | "APPROVED" | "POSTED" | "VOID";
export type PaymentAction =
  | "approve"
  | "generate-journal"
  | "void"
  | "reopen"
  | "unpost"
  | "cancel-posted";

export type PaymentAllocation = {
  id: number;
  supplier_invoice_id: number;
  invoice_number: string;
  supplier_invoice_number?: string | null;
  invoice_date?: string;
  due_date?: string | null;
  invoice_subtotal?: number;
  invoice_tax_amount?: number;
  invoice_total?: number;
  current_invoice_subtotal?: number;
  current_invoice_tax_amount?: number;
  current_invoice_total?: number;
  outstanding_balance?: number;
  current_available_balance?: number;
  allocated_amount: number;
  allocation_exception?: unknown;
  [key: string]: unknown;
};

export type PaymentFundingLine = {
  id: number;
  bank_name?: string;
  account_name?: string;
  account_number?: string;
  coa_account_code?: string | null;
  coa_account_name?: string | null;
  amount: number;
  [key: string]: unknown;
};

export type PaymentExceptionRow = Record<string, unknown>;

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
  status: PaymentStatus;
  notes?: string | null;
  source_type?: string | null;
  journal_entry_id?: number | null;
  journal_number?: string | null;
  business_unit_id?: number | null;
  location_id?: number | null;
  department_id?: number | null;
  allocations: PaymentAllocation[];
  funding_lines: PaymentFundingLine[];
  allowed_actions?: FinanceAllowedActions;
  activity_history?: FinanceActivityEvent[];
  allocation_exception_rows?: PaymentExceptionRow[];
};

export type EligiblePaymentSupplier = {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
};

export type PaymentQuery = FinancePageParams & {
  payment_status?: RawPaymentStatus;
};

export type PaymentPayload = {
  supplier_id: number;
  payment_date: string;
  payment_method: string;
  currency: string;
  total_amount: number;
  bank_charge_amount: number;
  short_over_amount: number;
  allocations: Array<{ supplier_invoice_id: number; allocated_amount: number; [key: string]: unknown }>;
  funding_lines: Array<{ bank_account_id: number; amount: number; [key: string]: unknown }>;
  bank_charge_account_id?: number | null;
  short_over_account_id?: number | null;
  difference_reason?: string | null;
  voucher_id?: number | null;
  reference_number?: string | null;
  cheque_number?: string | null;
  notes?: string | null;
  source_type?: string;
  [key: string]: unknown;
};

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

export type ReadyToPayPage = Pick<
  FinancePage<ReadyToPayInvoice>,
  "items" | "total_items" | "total_pages" | "has_next" | "has_previous"
> & {
  totals_by_currency: Record<string, number>;
};

export type PaymentListPage = FinancePage<Payment> & {
  summary?: { total_amount?: number; [key: string]: unknown };
};

export const listPayments = async (params: PaymentQuery = {}) =>
  (await api.get<PaymentListPage>("/payments", { params })).data;

export const listReadyToPay = async (
  params: { page?: number; page_size?: number; search?: string; currency?: string } = {},
) => (await api.get<ReadyToPayPage>("/payments/ready-to-pay", { params })).data;

export const getPayment = async (id: number) => (await api.get<Payment>(`/payments/${id}`)).data;

export const eligibleSuppliers = async (currency = "IDR", include_supplier_id?: number) =>
  (
    await api.get<EligiblePaymentSupplier[]>("/payments/eligible-suppliers", {
      params: { currency, include_supplier_id: include_supplier_id || undefined },
    })
  ).data;

export const eligibleInvoices = async (supplier_id: number, currency = "IDR") =>
  (
    await api.get<ReadyToPayInvoice[]>("/payments/eligible-invoices", {
      params: { supplier_id, currency },
    })
  ).data;

export const eligibleVouchers = async (supplier_id: number, currency = "IDR") =>
  (await api.get("/payments/eligible-vouchers", { params: { supplier_id, currency } })).data;

export const createPayment = async (payload: PaymentPayload) =>
  (await api.post<Payment>("/payments", payload)).data;

export const updatePayment = async (id: number, payload: PaymentPayload) =>
  (await api.patch<Payment>(`/payments/${id}`, payload)).data;

export const paymentAction = async (id: number, action: PaymentAction) =>
  (await api.post<Payment>(`/payments/${id}/${action}`)).data;

export const adminUnpostPayment = async (id: number) =>
  (await api.post(`/payments/${id}/unpost`)).data;

export const adminCancelPostedPayment = async (id: number) =>
  (await api.post(`/payments/${id}/cancel-posted`)).data;

export const adminReopenPayment = async (id: number) =>
  (await api.post(`/payments/${id}/reopen`)).data;
