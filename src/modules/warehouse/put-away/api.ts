import api from "@/api/client";

export const putAwayApi={

list:()=>

api.get("/put-away"),

detail:(id:number)=>

api.get(`/put-away/${id}`),

complete:(payload:any)=>

api.post("/put-away",payload),

};
