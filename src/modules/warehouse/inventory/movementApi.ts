import api from "@/api/client";

export const inventoryMovementApi={

list:()=>

api.get("/inventory/movements"),

};
