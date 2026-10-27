import api from "@/api/client";
export type OutletContext = { location_id: number; department_id: number };
export type OrderMode = "TABLE" | "COUNTER" | "EVENT";
export type OutletTable = { id: number; name: string; seats: number; is_active: boolean; status: "AVAILABLE" | "OCCUPIED"; order_id?: number };
export type Shift = { difference_reason?: string; cashier_name: string; location_name: string; outlet_name: string; id: number; cashier_id: number; status: "OPEN" | "CLOSED"; opening_cash: string; expected_cash: string; counted_cash: string | null; cash_difference: string | null; opened_at: string; closed_at?: string; open_orders: number; gross: string; service_charge: string; pbjt: string; payments: Record<string, string>; transactions: { id: number; number: string; method: string; total: string }[] };
export type OpenOrder = { id: number; number: string; table?: string; event?: string; cashier_id: number; total: string; session_id: number };
export type OperationsContext = { order_mode: OrderMode | null; tables: OutletTable[]; shifts: Shift[]; orders: OpenOrder[] };
export type OutletSetupRow = { id: number; name: string; code: string; parent_department_id: number; order_mode: OrderMode | null; is_active: boolean };
export type OutletSetupInput = { location_id: number; parent_department_id: number; name: string; code: string; order_mode: OrderMode; is_active: boolean };
export const operationsApi = {
  outlets: (location_id: number) => api.get<{ parents: { id: number; name: string }[]; outlets: OutletSetupRow[] }>("/pos-operations/outlets", { params: { location_id } }),
  saveOutlet: (values: OutletSetupInput, id?: number) => id ? api.put<OutletSetupRow>(`/pos-operations/outlets/${id}`, values) : api.post<OutletSetupRow>("/pos-operations/outlets", values),
  context: (scope: OutletContext) => api.get<OperationsContext>("/pos-operations/context", { params: scope }),
  policy: (scope: OutletContext, order_mode: OrderMode) => api.put("/pos-operations/policy", { ...scope, order_mode }),
  table: (scope: OutletContext, values: { name: string; seats: number; is_active: boolean }, id?: number) => id ? api.put(`/pos-operations/tables/${id}`, { ...scope, ...values }) : api.post("/pos-operations/tables", { ...scope, ...values }),
  openShift: (scope: OutletContext, opening_cash: string) => api.post<Shift>("/pos-operations/shifts", { ...scope, opening_cash }),
  shift: (id: number) => api.get<Shift>(`/pos-operations/shifts/${id}`),
  closeShift: (id: number, counted_cash: string, difference_reason: string) => api.post<Shift>(`/pos-operations/shifts/${id}/close`, { counted_cash, difference_reason }),
  report: (scope: OutletContext, date_from: string, date_to: string, cashier_id?: number) => api.get("/pos-operations/report", { params: { ...scope, date_from, date_to, cashier_id } }),
};
