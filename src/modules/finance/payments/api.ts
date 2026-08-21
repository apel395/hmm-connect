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
};

export const listPayments = async (params: any = {}) => (await api.get("/payments", { params })).data;
export const getPayment = async (id: number) => (await api.get<Payment>(`/payments/${id}`)).data;
export const eligibleInvoices = async (supplier_id: number, currency = "IDR") => (await api.get("/payments/eligible-invoices-available", { params: { supplier_id, currency } })).data;
export const createPayment = async (payload: any) => (await api.post<Payment>("/payments", payload)).data;
export const updatePayment = async (id: number, payload: any) => (await api.patch<Payment>(`/payments/${id}`, payload)).data;
export const paymentAction = async (id: number, action: string) => (await api.post<Payment>(`/payments/${id}/${action}`)).data;
export const adminUnpostPayment = async (id: number) => (await api.post(`/payments/${id}/unpost`)).data;
export const adminReopenPayment = async (id: number) => (await api.post(`/payments/${id}/reopen`)).data;
