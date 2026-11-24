import api from "@/api/client";

/** Query contract shared by cash-flow reports; modules may add extra filters. */
export type CashFlowQuery = {
  date_from?: string;
  date_to?: string;
  location_id?: number;
  business_unit_id?: number;
  department_id?: number;
  cash_account_id?: number;
  [key: string]: unknown;
};

export const getCashSummary = async (params: CashFlowQuery) => (await api.get("/cash-flow/summary", { params })).data;
export const getCashTimeline = async (params: CashFlowQuery) => (await api.get("/cash-flow/timeline", { params })).data;
export const getCashStatement = async (params: CashFlowQuery) =>
  (await api.get("/cash-flow/statement", { params: { ...params, date_from: params.date_from || undefined, date_to: params.date_to || undefined } })).data;
export const getCashAccounts = async (params: CashFlowQuery) => (await api.get("/cash-flow/accounts", { params })).data;
export const getCashActivity = async (id: number, params: CashFlowQuery) => (await api.get(`/cash-flow/accounts/${id}/activity`, { params })).data;
export const getCashTrace = async (id: number) => (await api.get(`/cash-flow/movements/${id}/trace`)).data;
export const listTransfers = async (params: CashFlowQuery) => (await api.get("/bank-transfers", { params })).data;
export const getTransfer = async (id: number) => (await api.get(`/bank-transfers/${id}`)).data;
export const getTransferPrint = async (id: number) => (await api.get(`/bank-transfers/${id}/print`)).data;
export const createTransfer = async (payload: Record<string, unknown>) => (await api.post("/bank-transfers", payload)).data;
export const updateTransfer = async (id: number, payload: Record<string, unknown>) => (await api.patch(`/bank-transfers/${id}`, payload)).data;
export const transferAction = async (id: number, action: string) => (await api.post(`/bank-transfers/${id}/${action}`)).data;
