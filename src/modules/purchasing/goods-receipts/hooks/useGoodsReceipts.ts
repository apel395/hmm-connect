import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";


import goodsReceiptApi from "../api/goodsReceiptApi";

import type {
  GoodsReceipt,
  GoodsReceiptCreatePayload,
} from "../types";

export function useAllGoodsReceipts() {
  return useQuery({
    queryKey: ["goods-receipts"],
    queryFn: async () => (await goodsReceiptApi.list()).data as GoodsReceipt[],
  });
}

export function useGoodsReceipt(id: number) {
  return useQuery({
    queryKey: ["goods-receipt", id],
    queryFn: async () => (await goodsReceiptApi.detail(id)).data as GoodsReceipt,
    enabled: Boolean(id),
  });
}


export function useGoodsReceipts(
  purchaseOrderId?: number
) {

  return useQuery({

    queryKey: [
      "goods-receipts",
      purchaseOrderId,
    ],

    queryFn: async () => {

      if (!purchaseOrderId) {
        return [];
      }

      const res =
        await goodsReceiptApi
          .listByPurchaseOrder(
            purchaseOrderId
          );

      return res.data;

    },

    enabled:
      !!purchaseOrderId,

  });

}



export function useReceiveGoods() {

  const qc =
    useQueryClient();


  return useMutation({

    mutationFn: ({
      purchaseOrderId,
      payload,
    }: {
      purchaseOrderId: number;

      payload: GoodsReceiptCreatePayload;
    }) =>
      goodsReceiptApi.receive(
        purchaseOrderId,
        payload
      ),


    onSuccess: (
      _,
      variables
    ) => {

      qc.invalidateQueries({
        queryKey: [
          "purchase-orders",
        ],
      });


      qc.invalidateQueries({
        queryKey: [
          "goods-receipts",
          variables.purchaseOrderId,
        ],
      });

    },

  });

}
