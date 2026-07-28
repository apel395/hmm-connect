import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  supplierApi,
  type SupplierPayload,
} from "../api/supplierApi";

export function useSuppliers() {
  return useQuery({
    queryKey: ["suppliers"],

    queryFn: async () => {
      const res =
        await supplierApi.list();

      return res.data;
    },
  });
}

export function useCreateSupplier() {
  const queryClient =
    useQueryClient();

  return useMutation({
    mutationFn: (
      payload: SupplierPayload
    ) =>
      supplierApi.create(
        payload
      ),

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "suppliers",
        ],
      });
    },
  });
}

export function useUpdateSupplier() {
  const queryClient =
    useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: SupplierPayload;
    }) =>
      supplierApi.update(
        id,
        payload
      ),

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "suppliers",
        ],
      });
    },
  });
}

export function useDeleteSupplier() {
  const queryClient =
    useQueryClient();

  return useMutation({
    mutationFn: (
      id: number
    ) =>
      supplierApi.remove(
        id
      ),

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "suppliers",
        ],
      });
    },
  });
}