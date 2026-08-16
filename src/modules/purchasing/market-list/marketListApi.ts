import api from "@/api/client";

export type MarketListParams = { scope?:"active"|"history"|"all"; page?:number; page_size?:number; search?:string; status?:string };

export const marketListApi = {
  list:(params:MarketListParams={})=>api.get("/market-lists",{params}),
  detail:(id:number)=>api.get(`/market-lists/${id}`),
  create:(payload:any)=>api.post("/market-lists",payload),
  update:(id:number,payload:any)=>api.put(`/market-lists/${id}`,payload),
  reopen:(id:number)=>api.post(`/market-lists/${id}/reopen`),
  submit:(id:number)=>api.post(`/market-lists/${id}/submit`),
  approve:(id:number,comment?:string)=>api.post(`/market-lists/${id}/approve`,{comment}),
  reject:(id:number,comment?:string)=>api.post(`/market-lists/${id}/reject`,{comment}),
  convertToPO:(id:number,supplier_id:number)=>api.post(`/market-lists/${id}/convert-to-po`,{supplier_id}),
};
