import api from "@/api/client";

import type {
  GoodsReceiptCreatePayload,
} from "../types";


export const goodsReceiptApi = {

  list: () => api.get("/goods-receipts"),

  detail: (id: number) => api.get(`/goods-receipts/${id}`),

  receivablePurchaseOrders: () => api.get("/goods-receipts/receivable-purchase-orders"),

  remainingItems: (purchaseOrderId: number) => api.get(`/goods-receipts/receivable-purchase-orders/${purchaseOrderId}/items`),

  listByPurchaseOrder: (
    purchaseOrderId: number
  ) =>
    api.get(
      "/goods-receipts",
      { params: { purchase_order_id: purchaseOrderId } }
    ),


  receive: (
    purchaseOrderId: number,
    payload: GoodsReceiptCreatePayload
  ) =>
    api.post(
      "/goods-receipts",
      {
        ...payload,
        purchase_order_id: purchaseOrderId,
      }
    ),

  post: (id: number) => api.post(`/goods-receipts/${id}/post`),

  allowedActions: (id: number) => api.get(`/goods-receipts/${id}/allowed-actions`),

};


export default goodsReceiptApi;
