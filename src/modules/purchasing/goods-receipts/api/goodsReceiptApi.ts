import api from "@/api/client";

import type {
  GoodsReceiptCreatePayload,
} from "../types";


export const goodsReceiptApi = {

  listByPurchaseOrder: (
    purchaseOrderId: number
  ) =>
    api.get(
      `/goods-receipts/purchase-orders/${purchaseOrderId}`
    ),


  receive: (
    purchaseOrderId: number,
    payload: GoodsReceiptCreatePayload
  ) =>
    api.post(
      `/goods-receipts/purchase-orders/${purchaseOrderId}/receive`,
      payload
    ),

};


export default goodsReceiptApi;