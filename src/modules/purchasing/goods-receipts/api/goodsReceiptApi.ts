import api from "@/api/client";

import type {
  GoodsReceiptCreatePayload,
} from "../types";


export const goodsReceiptApi = {

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

};


export default goodsReceiptApi;