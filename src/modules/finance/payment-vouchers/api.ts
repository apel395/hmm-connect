import api from "@/api/client";
import type {
  FinanceAllowedActions,
  FinancePage,
  FinancePageParams,
} from "@/modules/finance/types";

export type VoucherStatus =
  | "DRAFT"
  | "PENDING_APPROVAL"
  | "APPROVED"
  | "REJECTED"
  | "VOID"
  | "PAID";

export type VoucherInvoice = {
  id: number;
  invoice_number: string;
  supplier_invoice_number: string;
  invoice_date: string;
  due_date?: string | null;
  total_amount: number;
  allocated_amount: number;
};

export type VoucherGroup = {
  supplier_id: number;
  supplier_name: string;
  supplier_code: string;
  total: number;
  bank?: { bank_name: string; account_number: string; account_name: string } | null;
  invoices: VoucherInvoice[];
};

export type VoucherAllocation = {
  id: number;
  supplier_invoice_id: number;
  invoice_number: string;
  supplier_name: string;
  allocated_amount: number;
};

export type Voucher = {
  id: number;
  voucher_number: string;
  voucher_date: string;
  location_id: number;
  location_name?: string;
  status: VoucherStatus;
  total_amount: number;
  payment_id?: number | null;
  allowed_actions?: FinanceAllowedActions;
  period_from?: string;
  period_to?: string;
  groups?: VoucherGroup[];
  allocations: VoucherAllocation[];
};

export type EligibleInvoice = {
  id: number;
  invoice_number: string;
  supplier_invoice_number: string;
  supplier_id: number;
  supplier_name: string;
  invoice_date: string;
  due_date: string;
  total_amount: number;
  available_balance: number;
};

export type VoucherListParams = FinancePageParams & {
  date_from?: string;
  date_to?: string;
  location_id?: number;
};

export type CreateVoucherPayload = {
  location_id: number;
  voucher_date: string;
  allocations: Array<{ supplier_invoice_id: number; allocated_amount: number }>;
  notes?: string;
};

export const listVouchers = async (params: VoucherListParams = {}) =>
  (await api.get<FinancePage<Voucher>>("/payment-vouchers", { params })).data;
export const getVoucher = async (id: number) => (await api.get<Voucher>(`/payment-vouchers/${id}`)).data;
export const createVoucher = async (data: CreateVoucherPayload) =>
  (await api.post<Voucher>("/payment-vouchers", data)).data;
export const submitVoucher = async (id: number) =>
  (await api.post<Voucher>(`/payment-vouchers/${id}/submit`)).data;
export const approveVoucher = async (id: number) =>
  (await api.post<Voucher>(`/payment-vouchers/${id}/approve`)).data;
export const rejectVoucher = async (id: number, reason: string) =>
  (await api.post<Voucher>(`/payment-vouchers/${id}/reject`, { reason })).data;
export const voidVoucher = async (id: number) =>
  (await api.post<Voucher>(`/payment-vouchers/${id}/void`)).data;
export const getVoucherPrint = (id: number) => api.get(`/payment-vouchers/${id}/print`);
export const listEligibleInvoices = async (location_id: number, supplier_id?: number) =>
  (
    await api.get<EligibleInvoice[]>("/payment-vouchers/eligible-invoices", {
      params: { location_id, supplier_id },
    })
  ).data;
