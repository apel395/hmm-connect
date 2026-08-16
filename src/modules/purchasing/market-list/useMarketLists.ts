import { useMutation,useQuery,useQueryClient } from "@tanstack/react-query";
import { marketListApi,type MarketListParams } from "./marketListApi";

async function refresh(qc:ReturnType<typeof useQueryClient>,id?:number,detail?:unknown){
 if(id&&detail)qc.setQueryData(["market-list",id],detail);
 await Promise.all([
  qc.invalidateQueries({queryKey:["market-lists"]}),
  qc.invalidateQueries({queryKey:["approval-inbox"]}),
  id?qc.invalidateQueries({queryKey:["approval","MARKET_LIST",id]}):Promise.resolve(),
 ]);
}
export function useMarketLists(params:MarketListParams={scope:"active"}){return useQuery({queryKey:["market-lists",params],queryFn:async()=>(await marketListApi.list(params)).data,placeholderData:(previous)=>previous})}
export function useMarketList(id:number){return useQuery({queryKey:["market-list",id],queryFn:async()=>(await marketListApi.detail(id)).data,enabled:Boolean(id)})}
export function useCreateMarketList(){const qc=useQueryClient();return useMutation({mutationFn:(payload:any)=>marketListApi.create(payload),onSuccess:()=>refresh(qc)})}
export function useUpdateMarketList(){const qc=useQueryClient();return useMutation({mutationFn:({id,payload}:{id:number;payload:any})=>marketListApi.update(id,payload),onSuccess:(r,v)=>refresh(qc,v.id,r.data)})}
export function useSubmitMarketList(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>marketListApi.submit(id),onSuccess:(r,id)=>refresh(qc,id,r.data)})}
export function useApproveMarketList(){const qc=useQueryClient();return useMutation({mutationFn:({id,comment}:{id:number;comment?:string})=>marketListApi.approve(id,comment),onSuccess:(r,v)=>refresh(qc,v.id,r.data)})}
export function useRejectMarketList(){const qc=useQueryClient();return useMutation({mutationFn:({id,comment}:{id:number;comment:string})=>marketListApi.reject(id,comment),onSuccess:(r,v)=>refresh(qc,v.id,r.data)})}
export function useReopenMarketList(){const qc=useQueryClient();return useMutation({mutationFn:(id:number)=>marketListApi.reopen(id),onSuccess:(r,id)=>refresh(qc,id,r.data)})}
export function useConvertMarketList(){const qc=useQueryClient();return useMutation({mutationFn:({id,supplier_id}:{id:number;supplier_id:number})=>marketListApi.convertToPO(id,supplier_id),onSuccess:async()=>{await Promise.all([qc.invalidateQueries({queryKey:["market-lists"]}),qc.invalidateQueries({queryKey:["purchase-orders"]})])}})}
