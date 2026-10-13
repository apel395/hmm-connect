import api from "@/api/client";

export const listAssets = async (params: any = {}) => (await api.get("/fixed-assets", { params })).data;
export const getAsset = async (id: number) => (await api.get(`/fixed-assets/${id}`)).data;
export const createAsset = async (data: any) => (await api.post("/fixed-assets", data)).data;
export const assetAction = async (id: number, action: string, data: any = {}) => (await api.post(`/fixed-assets/${id}/${action}`, data)).data;
export const listCategories = async () => (await api.get("/fixed-assets/categories")).data;
export const saveCategory = async (data: any) => (await api[data.id ? "patch" : "post"](data.id ? `/fixed-assets/categories/${data.id}` : "/fixed-assets/categories", data)).data;
export const listRuns = async () => (await api.get("/fixed-assets/depreciation-runs")).data;
export const createRun = async (data: any) => (await api.post("/fixed-assets/depreciation-runs", data)).data;
export const runAction = async (id: number, action: string) => (await api.post(`/fixed-assets/depreciation-runs/${id}/${action}`)).data;
export const getAssetReport = async (params: any) => (await api.get("/reports/fixed-assets", { params })).data;
export const getDepreciationReport = async (params: any) => (await api.get("/reports/depreciation", { params })).data;

export const listAmortizations = async () => (await api.get("/amortizations")).data;
export const createAmortization = async (data: any) => (await api.post("/amortizations", data)).data;
export const updateAmortization = async (id: number, data: any) => (await api.patch(`/amortizations/${id}`, data)).data;
export const postNextAmortization = async (item: {id:number;months_posted:number}) => (await api.post(`/amortizations/${item.id}/post-next`,null,{params:{expected_months_posted:item.months_posted}})).data;
export const unpostLastAmortization = async (item: {id:number;months_posted:number}) => (await api.post(`/amortizations/${item.id}/unpost-last`,null,{params:{expected_months_posted:item.months_posted}})).data;
export const getAmortizationSchedule = async (id:number) => (await api.get(`/amortizations/${id}/schedule`)).data;

export const syncInvoiceAssets = async () => (await api.post<{ registered: number }>("/fixed-assets/sync-invoice-assets")).data;
