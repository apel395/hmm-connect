import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import goodsReceiptApi, { type GoodsReceiptListParams } from "../api/goodsReceiptApi";
import type { GoodsReceipt, GoodsReceiptCostCorrectionPayload, GoodsReceiptCreatePayload } from "../types";

export function useAllGoodsReceipts(params: GoodsReceiptListParams = {}) {
  return useQuery({ queryKey: ["goods-receipts", params], queryFn: async () => (await goodsReceiptApi.list(params)).data });
}
export function useGoodsReceipt(id:number){return useQuery({queryKey:["goods-receipt",id],queryFn:async()=>(await goodsReceiptApi.detail(id)).data as GoodsReceipt,enabled:Boolean(id)})}
export function useReceivablePurchaseOrders(enabled=true){return useQuery({queryKey:["receivable-purchase-orders"],queryFn:async()=>(await goodsReceiptApi.receivablePurchaseOrders()).data,enabled})}
export function useRemainingPurchaseOrderItems(purchaseOrderId?:number){return useQuery({queryKey:["remaining-purchase-order-items",purchaseOrderId],queryFn:async()=>(await goodsReceiptApi.remainingItems(purchaseOrderId!)).data,enabled:Boolean(purchaseOrderId)})}
export function useGoodsReceipts(purchaseOrderId?:number){return useQuery({queryKey:["goods-receipts-by-po",purchaseOrderId],queryFn:async()=>purchaseOrderId?((await goodsReceiptApi.listByPurchaseOrder(purchaseOrderId)).data?.items ?? []):[],enabled:!!purchaseOrderId})}

const invalidateReceipt=(qc:any,id?:number)=>{if(id)qc.invalidateQueries({queryKey:["goods-receipt",id]});qc.invalidateQueries({queryKey:["goods-receipts"]});qc.invalidateQueries({queryKey:["receivable-purchase-orders"]});qc.invalidateQueries({queryKey:["purchase-orders"]});};
export function useReceiveGoods(){const qc=useQueryClient();return useMutation({mutationFn:async({purchaseOrderId,payload}:{purchaseOrderId?:number;payload:GoodsReceiptCreatePayload})=>purchaseOrderId?goodsReceiptApi.receive(purchaseOrderId,payload):goodsReceiptApi.createDirect(payload),onSuccess:(response,variables)=>{const id=response.data?.id;invalidateReceipt(qc,id);if(variables.purchaseOrderId){qc.invalidateQueries({queryKey:["remaining-purchase-order-items",variables.purchaseOrderId]});qc.invalidateQueries({queryKey:["goods-receipts-by-po",variables.purchaseOrderId]})}}})}
export function useSubmitGoodsReceipt(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>goodsReceiptApi.submit(id),onSuccess:(_,id)=>invalidateReceipt(qc,id)})}
export function useApproveGoodsReceipt(){const qc=useQueryClient();return useMutation({mutationFn:({id,comment}:{id:number;comment?:string})=>goodsReceiptApi.approve(id,comment),onSuccess:(_,v)=>invalidateReceipt(qc,v.id)})}
export function useRejectGoodsReceipt(){const qc=useQueryClient();return useMutation({mutationFn:({id,comment}:{id:number;comment:string})=>goodsReceiptApi.reject(id,comment),onSuccess:(_,v)=>invalidateReceipt(qc,v.id)})}
export function usePostGoodsReceipt(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>goodsReceiptApi.post(id),onSuccess:(_,id)=>{invalidateReceipt(qc,id);qc.invalidateQueries({queryKey:["inventory"]});qc.invalidateQueries({queryKey:["inventory-movements"]})}})}
export function useCorrectGoodsReceiptCosts(){const qc=useQueryClient();return useMutation({mutationFn:({id,payload}:{id:number;payload:GoodsReceiptCostCorrectionPayload})=>goodsReceiptApi.correctCosts(id,payload),onSuccess:(_,variables)=>{qc.invalidateQueries({queryKey:["goods-receipt",variables.id]});qc.invalidateQueries({queryKey:["goods-receipts"]});qc.invalidateQueries({queryKey:["inventory"]});qc.invalidateQueries({queryKey:["inventory-movements"]})}})}
export function useReturnGoodsReceipt(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>goodsReceiptApi.returnReceipt(id),onSuccess:(_,id)=>{invalidateReceipt(qc,id);qc.invalidateQueries({queryKey:["inventory"]});qc.invalidateQueries({queryKey:["inventory-movements"]})}})}
