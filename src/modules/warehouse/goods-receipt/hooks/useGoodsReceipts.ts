import{

useMutation,

useQuery,

useQueryClient,

}from"@tanstack/react-query";

import{

goodsReceiptApi,

}from"../api/goodsReceiptApi";

export function useGoodsReceipts(){

return useQuery({

queryKey:["goods-receipts"],

queryFn:async()=>{

const res=

await goodsReceiptApi.list();

return res.data;

},

});

}

export function useGoodsReceipt(id:number){

return useQuery({

queryKey:["goods-receipt",id],

queryFn:async()=>{

const res=

await goodsReceiptApi.detail(id);

return res.data;

},

enabled:!!id,

});

}

export function useReceiveGoods(){

const qc=useQueryClient();

return useMutation({

mutationFn:(payload:any)=>

goodsReceiptApi.receive(payload),

onSuccess(){

qc.invalidateQueries();

},

});

}

export function useCompleteReceipt(){

const qc=useQueryClient();

return useMutation({

mutationFn:(id:number)=>

goodsReceiptApi.complete(id),

onSuccess(){

qc.invalidateQueries();

},

});

}
