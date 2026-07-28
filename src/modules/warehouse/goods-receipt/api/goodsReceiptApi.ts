import api from "@/api/client";

export const goodsReceiptApi={

list:()=>

api.get("/goods-receipts"),

detail:(id:number)=>

api.get(`/goods-receipts/${id}`),

receive:(payload:any)=>

api.post("/goods-receipts",payload),

complete:(id:number)=>

api.post(`/goods-receipts/${id}/complete`),

};
