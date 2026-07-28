import api from "@/api/client";

export const inventoryApi={

list:()=>

api.get("/inventory"),

detail:(id:number)=>

api.get(`/inventory/${id}`),

movement:(id:number)=>

api.get(`/inventory/${id}/movements`),

};
