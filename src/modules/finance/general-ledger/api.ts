import api from "@/api/client";

export const listLedger = async (params: any) => (await api.get("/general-ledger", { params })).data;
export const getAccountSummary = async (accountId: number, params: any) => (await api.get(`/general-ledger/accounts/${accountId}/summary`, { params })).data;

export const exportGeneralLedgerXlsx = async (params: Record<string, unknown>) => {
  const exportParams = Object.fromEntries(Object.entries(params).filter(([key, value]) => key !== "page" && key !== "page_size" && value !== "" && value != null));
  const response = await api.get("/general-ledger/export", { params: exportParams, responseType: "blob" });
  const disposition = String(response.headers["content-disposition"] || "");
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = match?.[1] || "general-ledger.xlsx";
  link.click();
  URL.revokeObjectURL(url);
};
