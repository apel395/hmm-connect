import type { CheckoutOptions, CheckoutConfiguration } from "./checkoutTypes";
import api from "@/api/client";
export type OutletContext = { location_id: number; department_id: number };
export type OrderMode = "TABLE" | "COUNTER" | "EVENT";
export type OutletTable = { id: number; name: string; seats: number; is_active: boolean; status: "AVAILABLE" | "OCCUPIED"; order_id?: number | null };
export type OutletPayments = Record<"CASH" | "CARD" | "BANK_TRANSFER", string>;
export type CashierTotal = { cashier_id: number; name: string; sales: number; gross: string };
export type OutletTotals = {
  sales: number;
  gross: string;
  subtotal: string;
  discount: string;
  service_charge: string;
  pbjt: string;
  other_tax: string;
  payments: OutletPayments;
  cashiers: CashierTotal[];
};
export type Shift = {
  difference_reason?: string | null;
  cashier_name: string;
  location_name: string;
  outlet_name: string;
  id: number;
  cashier_id: number;
  status: "OPEN" | "CLOSED";
  opening_cash: string;
  expected_cash: string;
  counted_cash: string | null;
  cash_difference: string | null;
  opened_at: string;
  closed_at?: string | null;
  open_orders: number;
  gross: string;
  service_charge: string;
  pbjt: string;
  payments: OutletPayments;
  transactions: { id: number; number: string; method: string; total: string; date?: string }[];
};
export type OpenOrder = { guest_count?: number | null; id: number; number: string; table?: string | null; event?: string | null; cashier_id: number; total: string; session_id: number; date?: string | null };
export type OperationsContext = { order_mode: OrderMode | null; tables: OutletTable[]; shifts: Shift[]; orders: OpenOrder[] };
export type OutletSetupRow = { id: number; name: string; code: string; parent_department_id: number; order_mode: OrderMode | null; is_active: boolean };
export type OutletSetupInput = { location_id: number; parent_department_id: number; name: string; code: string; order_mode: OrderMode; is_active: boolean };
export type OutletReport = OutletTotals & {
  location: string;
  outlet: string;
  date_from: string;
  date_to: string;
  daily: (OutletTotals & { date: string })[];
};
export type OutletPolicy = { order_mode: OrderMode };
export type OutletTableResult = { id: number; name: string; is_active?: boolean };
export const operationsApi = {
  checkoutOptions: (scope:OutletContext)=>api.get<CheckoutOptions>("/pos-operations/checkout-options",{params:scope}),
  checkoutSettings: (scope:OutletContext)=>api.get<CheckoutOptions>("/pos-operations/checkout-settings",{params:scope}),
  saveCheckoutSettings: (scope:OutletContext,configuration:CheckoutConfiguration,version:string)=>api.put<CheckoutOptions>("/pos-operations/checkout-settings",{...scope,configuration,version}),
  outlets: (location_id: number) => api.get<{ parents: { id: number; name: string }[]; outlets: OutletSetupRow[] }>("/pos-operations/outlets", { params: { location_id } }),
  saveOutlet: (values: OutletSetupInput, id?: number) => id ? api.put<OutletSetupRow>(`/pos-operations/outlets/${id}`, values) : api.post<OutletSetupRow>("/pos-operations/outlets", values),
  context: (scope: OutletContext) => api.get<OperationsContext>("/pos-operations/context", { params: scope }),
  policy: (scope: OutletContext, order_mode: OrderMode) => api.put<OutletPolicy>("/pos-operations/policy", { ...scope, order_mode }),
  table: (scope: OutletContext, values: { name: string; seats: number; is_active: boolean }, id?: number) => id ? api.put<OutletTableResult>(`/pos-operations/tables/${id}`, { ...scope, ...values }) : api.post<OutletTableResult>("/pos-operations/tables", { ...scope, ...values }),
  openShift: (scope: OutletContext, opening_cash: string) => api.post<Shift>("/pos-operations/shifts", { ...scope, opening_cash }),
  shift: (id: number) => api.get<Shift>(`/pos-operations/shifts/${id}`),
  closeShift: (id: number, counted_cash: string, difference_reason: string) => api.post<Shift>(`/pos-operations/shifts/${id}/close`, { counted_cash, difference_reason }),
  report: (scope: OutletContext, date_from: string, date_to: string, cashier_id?: number) => api.get<OutletReport>("/pos-operations/report", { params: { ...scope, date_from, date_to, cashier_id } }),
};
