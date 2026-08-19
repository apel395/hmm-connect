import api from "@/api/client";

export const listLedger = async (params: any) => (await api.get("/general-ledger", { params })).data;
export const getAccountSummary = async (accountId: number, params: any) => (await api.get(`/general-ledger/accounts/${accountId}/summary`, { params })).data;
