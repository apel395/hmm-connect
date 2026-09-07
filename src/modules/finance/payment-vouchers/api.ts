import api from "@/api/client";

export type Voucher = {
  id: number;
  voucher_number: string;
  voucher_date: string;
  location_id: number;
  location_name?: string;
  status: string;
  total_amount: number;
  period_from?: string;
  period_to?: string;
  groups?: Array<{
    supplier_id: number;
    supplier_name: string;
    supplier_code: string;
    total: number;
    bank?: { bank_name: string; account_number: string; account_name: string } | null;
    invoices: Array<{ id: number; invoice_number: string; supplier_invoice_number: string; invoice_date: string; total_amount: number; allocated_amount: number }>;
  }>;
  allocations: Array<{ id: number; supplier_invoice_id: number; invoice_number: string; supplier_name: string; allocated_amount: number }>;
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

export const listVouchers = (params: Record<string, unknown>) => api.get("/payment-vouchers", { params });
export const getVoucher = (id: number) => api.get(`/payment-vouchers/${id}`);
export const createVoucher = (data: unknown) => api.post("/payment-vouchers", data);
export const submitVoucher = (id: number) => api.post(`/payment-vouchers/${id}/submit`);
export const approveVoucher = (id: number) => api.post(`/payment-vouchers/${id}/approve`);
export const rejectVoucher = (id: number, reason?: string) => api.post(`/payment-vouchers/${id}/reject`, { reason });
export const voidVoucher = (id: number) => api.post(`/payment-vouchers/${id}/void`);
export const getVoucherPrint = (id: number) => api.get(`/payment-vouchers/${id}/print`);
export const listEligibleInvoices = (location_id: number, supplier_id?: number) =>
  api.get("/payment-vouchers/eligible-invoices", { params: { location_id, supplier_id } });
