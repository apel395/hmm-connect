import api from "@/api/client";

export const listLedger = async (params: any) => (await api.get("/general-ledger", { params })).data;
export const getAccountSummary = async (accountId: number, params: any) => (await api.get(`/general-ledger/accounts/${accountId}/summary`, { params })).data;
export const getLedgerPrint = async (params: any) => (await api.get("/general-ledger/print", { params })).data;
export const createLedgerExport = async (params: any) => (await api.post("/exports", { export_type: "general_ledger", params })).data;
export const getExport = async (jobId: string) => (await api.get(`/exports/${jobId}`)).data;