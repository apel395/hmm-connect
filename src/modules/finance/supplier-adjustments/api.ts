import api from "@/api/client";

export type SupplierAdjustment = {
  id: number;
  adjustment_number: string;
  adjustment_type: "CREDIT_NOTE" | "DEBIT_NOTE";
  supplier_invoice_id: number;
  invoice_number?: string | null;
  supplier_invoice_number?: string | null;
  supplier_id: number;
  supplier_name?: string | null;
  adjustment_date: string;
  amount: number;
  adjustment_account_id: number;
  adjustment_account_code?: string | null;
  adjustment_account_name?: string | null;
  reason: string;
  notes?: string | null;
  status: string;
  journal_entry_id?: number | null;
  journal_number?: string | null;
  allowed_actions?: Record<string, boolean>;
};

export const listSupplierAdjustments = async (params: any = {}) =>
  (await api.get("/supplier-adjustments", { params })).data;

export const createSupplierAdjustment = async (payload: any) =>
  (await api.post<SupplierAdjustment>("/supplier-adjustments", payload)).data;

export const supplierAdjustmentAction = async (id: number, action: "generate-journal" | "void") =>
  (await api.post<SupplierAdjustment>(`/supplier-adjustments/${id}/${action}`)).data;
