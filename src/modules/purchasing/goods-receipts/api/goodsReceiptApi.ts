import api from "@/api/client";
import type { GoodsReceiptCostCorrectionPayload, GoodsReceiptCreatePayload, GoodsReceiptUpdatePayload } from "../types";

export type GoodsReceiptListParams = {
  page?: number;
  page_size?: number;
  search?: string;
  destination_type?: string;
  status?: string;
  approval_status?: string;
  purchase_order_id?: number;
  date_from?: string;
  date_to?: string;
};

export const goodsReceiptApi = {
  list: (params: GoodsReceiptListParams = {}) => api.get("/goods-receipts", { params }),
  detail: (id: number) => api.get(`/goods-receipts/${id}`),
  receivablePurchaseOrders: (params: { date_from?: string; date_to?: string } = {}) => api.get("/goods-receipts/receivable-purchase-orders", { params }),
  remainingItems: (purchaseOrderId: number) => api.get(`/goods-receipts/receivable-purchase-orders/${purchaseOrderId}/items`),
  listByPurchaseOrder: (purchaseOrderId: number) => api.get("/goods-receipts", { params: { purchase_order_id: purchaseOrderId, page: 1, page_size: 100 } }),
  receive: (purchaseOrderId: number, payload: GoodsReceiptCreatePayload) => api.post("/goods-receipts", { ...payload, purchase_order_id: purchaseOrderId }),
  createDirect: (payload: GoodsReceiptCreatePayload) => api.post("/goods-receipts", { ...payload, purchase_order_id: null }),
  update: (id: number, payload: GoodsReceiptUpdatePayload) => api.put(`/goods-receipts/${id}`, payload),
  submit: (id: number) => api.post(`/goods-receipts/${id}/submit`),
  approve: (id: number, comment?: string) => api.post(`/goods-receipts/${id}/approve`, comment ? { comment } : {}),
  reject: (id: number, comment: string) => api.post(`/goods-receipts/${id}/reject`, { comment }),
  post: (id: number) => api.post(`/goods-receipts/${id}/post`),
  correctCosts: (id: number, payload: GoodsReceiptCostCorrectionPayload) => api.patch(`/goods-receipts/${id}/costs`, payload),
  returnReceipt: (id: number) => api.post(`/goods-receipts/${id}/return`),
  allowedActions: (id: number) => api.get(`/goods-receipts/${id}/allowed-actions`),
};

export default goodsReceiptApi;
