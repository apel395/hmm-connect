import api from "@/api/client";
import type { GoodsReceiptCostCorrectionPayload, GoodsReceiptCreatePayload, GoodsReceiptUpdatePayload, HistoricalReceiptCorrectionPayload } from "../types";

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

export type ReceivedItemHistoryRow = {
  goods_receipt_item_id: number;
  goods_receipt_id: number;
  receipt_number: string;
  received_at: string;
  status: string;
  supplier_name: string | null;
  product_id: number;
  product_code: string;
  product_name: string;
  uom: string | null;
  quantity: number;
  unit_cost: number;
  line_subtotal: number;
};

export type ReceivedItemHistoryResponse = {
  items: ReceivedItemHistoryRow[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
};

export const goodsReceiptApi = {
  list: (params: GoodsReceiptListParams = {}) => api.get("/goods-receipts", { params }),
  itemHistory: (search: string, page = 1, pageSize = 50) =>
    api.get<ReceivedItemHistoryResponse>("/goods-receipts/item-history", { params: { search, page, page_size: pageSize } }),
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
  depost: (id:number,reason:string) => api.post(`/goods-receipts/${id}/unpost`,{reason}),
  correctCosts: (id: number, payload: GoodsReceiptCostCorrectionPayload) => api.patch(`/goods-receipts/${id}/costs`, payload),
  correctHistorical: (id: number, payload: HistoricalReceiptCorrectionPayload) => api.patch(`/goods-receipts/${id}/historical-correction`, payload),
  returnReceipt: (id: number) => api.post(`/goods-receipts/${id}/return`),
  allowedActions: (id: number) => api.get(`/goods-receipts/${id}/allowed-actions`),
};

export default goodsReceiptApi;
