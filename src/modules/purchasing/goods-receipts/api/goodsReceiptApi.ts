import api from "@/api/client";
import type { GoodsReceiptCostCorrectionPayload, GoodsReceiptCreatePayload } from "../types";

export const goodsReceiptApi = {
  list: () => api.get("/goods-receipts"),
  detail: (id: number) => api.get(`/goods-receipts/${id}`),
  receivablePurchaseOrders: () => api.get("/goods-receipts/receivable-purchase-orders"),
  remainingItems: (purchaseOrderId: number) => api.get(`/goods-receipts/receivable-purchase-orders/${purchaseOrderId}/items`),
  listByPurchaseOrder: (purchaseOrderId: number) => api.get("/goods-receipts", { params: { purchase_order_id: purchaseOrderId } }),
  receive: (purchaseOrderId: number, payload: GoodsReceiptCreatePayload) => api.post("/goods-receipts", { ...payload, purchase_order_id: purchaseOrderId }),
  createDirect: (payload: GoodsReceiptCreatePayload) => api.post("/goods-receipts", { ...payload, purchase_order_id: null }),
  submit: (id: number) => api.post(`/goods-receipts/${id}/submit`),
  approve: (id: number, comment?: string) => api.post(`/goods-receipts/${id}/approve`, comment ? { comment } : {}),
  reject: (id: number, comment: string) => api.post(`/goods-receipts/${id}/reject`, { comment }),
  post: (id: number) => api.post(`/goods-receipts/${id}/post`),
  correctCosts: (id: number, payload: GoodsReceiptCostCorrectionPayload) => api.patch(`/goods-receipts/${id}/costs`, payload),
  returnReceipt: (id: number) => api.post(`/goods-receipts/${id}/return`),
  allowedActions: (id: number) => api.get(`/goods-receipts/${id}/allowed-actions`),
};

export default goodsReceiptApi;
