import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import warehouseApi from "../api/warehouseApi";
import type { Warehouse, WarehousePayload, WarehouseUpdatePayload } from "../types";

export function useWarehouses(){return useQuery({queryKey:["warehouses"],queryFn:async()=>{const res=await warehouseApi.list();const value=res.data as Warehouse[]|{items?:Warehouse[];data?:Warehouse[]};if(Array.isArray(value))return value;if(Array.isArray(value.items))return value.items;if(Array.isArray(value.data))return value.data;return [];}})}
export function useCreateWarehouse(){const qc=useQueryClient();return useMutation({mutationFn:(payload:WarehousePayload)=>warehouseApi.create(payload),onSuccess(){qc.invalidateQueries({queryKey:["warehouses"]});}})}
export function useUpdateWarehouse(){const qc=useQueryClient();return useMutation({mutationFn:({id,payload}:{id:number;payload:WarehouseUpdatePayload})=>warehouseApi.update(id,payload),onSuccess(){qc.invalidateQueries({queryKey:["warehouses"]});}})}
