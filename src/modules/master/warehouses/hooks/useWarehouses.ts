import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import warehouseApi from "../api/warehouseApi";

import type {
  WarehousePayload,
} from "../types";


export function useWarehouses() {
  return useQuery({
    queryKey: [
      "warehouses",
    ],

    queryFn: async () => {
      const res =
        await warehouseApi.list();

      return res.data;
    },
  });
}


export function useCreateWarehouse() {
  const qc =
    useQueryClient();

  return useMutation({
    mutationFn: (
      payload: WarehousePayload
    ) =>
      warehouseApi.create(
        payload
      ),

    onSuccess() {
      qc.invalidateQueries({
        queryKey: [
          "warehouses",
        ],
      });
    },
  });
}
