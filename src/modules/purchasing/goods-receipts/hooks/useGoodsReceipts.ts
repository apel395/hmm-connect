import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import goodsReceiptApi, { type GoodsReceiptListParams } from "../api/goodsReceiptApi";
import type { GoodsReceipt, GoodsReceiptCostCorrectionPayload, GoodsReceiptCreatePayload } from "../types";

export function useAllGoodsReceipts(params: GoodsReceiptListParams = {}) {
  return useQuery({ queryKey: ["goods-receipts", params], queryFn: async () => (await goodsReceiptApi.list(params)).data, placeholderData: (previous) => previous });
}
export function useGoodsReceipt(id:number){return useQuery({queryKey:["goods-receipt",id],queryFn:async()=>(await goodsReceiptApi.detail(id)).data as GoodsReceipt,enabled:Boolean(id)})}
export function useReceivablePurchaseOrders(enabled=true){return useQuery({queryKey:["receivable-purchase-orders"],queryFn:async()=>(await goodsReceiptApi.receivablePurchaseOrders()).data,enabled})}
export function useRemainingPurchaseOrderItems(purchaseOrderId?:number){return useQuery({queryKey:["remaining-purchase-order-items",purchaseOrderId],queryFn:async()=>(await goodsReceiptApi.remainingItems(purchaseOrderId!)).data,enabled:Boolean(purchaseOrderId)})}
export function useGoodsReceipts(purchaseOrderId?:number){return useQuery({queryKey:["goods-receipts-by-po",purchaseOrderId],queryFn:async()=>purchaseOrderId?((await goodsReceiptApi.listByPurchaseOrder(purchaseOrderId)).data?.items ?? []):[],enabled:!!purchaseOrderId})}

async function invalidateReceipt(qc:ReturnType<typeof useQueryClient>,id?:number,detail?:unknown){
  if(id&&detail)qc.setQueryData(["goods-receipt",id],detail);
  await Promise.all([
    id?qc.refetchQueries({queryKey:["goods-receipt",id],exact:true,type:"active"}):Promise.resolve(),
    qc.invalidateQueries({queryKey:["goods-receipts"]}),
    qc.invalidateQueries({queryKey:["receivable-purchase-orders"]}),
    qc.invalidateQueries({queryKey:["purchase-orders"]}),
    qc.invalidateQueries({queryKey:["approval"]}),
    qc.invalidateQueries({queryKey:["approval-inbox"]}),
  ]);
}
export function useReceiveGoods(){const qc=useQueryClient();return useMutation({mutationFn:async({purchaseOrderId,payload}:{purchaseOrderId?:number;payload:GoodsReceiptCreatePayload})=>purchaseOrderId?goodsReceiptApi.receive(purchaseOrderId,payload):goodsReceiptApi.createDirect(payload),onSuccess:async(response,variables)=>{const id=response.data?.id;await invalidateReceipt(qc,id,response.data);if(variables.purchaseOrderId){await Promise.all([qc.invalidateQueries({queryKey:["remaining-purchase-order-items",variables.purchaseOrderId]}),qc.invalidateQueries({queryKey:["goods-receipts-by-po",variables.purchaseOrderId]})])}}})}
export function useSubmitGoodsReceipt(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>goodsReceiptApi.submit(id),onSuccess:(response,id)=>invalidateReceipt(qc,id,response.data)})}
export function useApproveGoodsReceipt(){const qc=useQueryClient();return useMutation({mutationFn:({id,comment}:{id:number;comment?:string})=>goodsReceiptApi.approve(id,comment),onSuccess:(response,v)=>invalidateReceipt(qc,v.id,response.data)})}
export function useRejectGoodsReceipt(){const qc=useQueryClient();return useMutation({mutationFn:({id,comment}:{id:number;comment:string})=>goodsReceiptApi.reject(id,comment),onSuccess:(response,v)=>invalidateReceipt(qc,v.id,response.data)})}
export function usePostGoodsReceipt(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>goodsReceiptApi.post(id),onSuccess:async(response,id)=>{await invalidateReceipt(qc,id,response.data);await Promise.all([qc.invalidateQueries({queryKey:["inventory"]}),qc.invalidateQueries({queryKey:["inventory-movements"]})])}})}
export function useCorrectGoodsReceiptCosts(){const qc=useQueryClient();return useMutation({mutationFn:({id,payload}:{id:number;payload:GoodsReceiptCostCorrectionPayload})=>goodsReceiptApi.correctCosts(id,payload),onSuccess:async(response,variables)=>{qc.setQueryData(["goods-receipt",variables.id],response.data);await Promise.all([qc.refetchQueries({queryKey:["goods-receipt",variables.id],exact:true,type:"active"}),qc.invalidateQueries({queryKey:["goods-receipts"]}),qc.invalidateQueries({queryKey:["inventory"]}),qc.invalidateQueries({queryKey:["inventory-movements"]})])}})}
export function useReturnGoodsReceipt(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>goodsReceiptApi.returnReceipt(id),onSuccess:async(response,id)=>{await invalidateReceipt(qc,id,response.data);await Promise.all([qc.invalidateQueries({queryKey:["inventory"]}),qc.invalidateQueries({queryKey:["inventory-movements"]})])}})}
