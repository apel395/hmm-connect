import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { supplierApi } from "../api/supplierApi";
import type { SupplierPayload } from "../types";

export const supplierKeys = {
  all: ["suppliers"] as const,
  lists: () => [...supplierKeys.all, "list"] as const,
  detail: (id: number) => [...supplierKeys.all, "detail", id] as const,
};

export function useSuppliers() {
  return useQuery({
    queryKey: supplierKeys.lists(),
    queryFn: supplierApi.list,
  });
}

export function useSupplier(id?: number) {
  return useQuery({
    queryKey: supplierKeys.detail(id ?? 0),
    queryFn: () => supplierApi.detail(id as number),
    enabled: id !== undefined,
  });
}

function useInvalidateSuppliers() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: supplierKeys.all });
}

export function useCreateSupplier() {
  const invalidate = useInvalidateSuppliers();
  return useMutation({
    mutationFn: (payload: SupplierPayload) => supplierApi.create(payload),
    onSuccess: invalidate,
  });
}

export function useUpdateSupplier() {
  const invalidate = useInvalidateSuppliers();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: SupplierPayload }) =>
      supplierApi.update(id, payload),
    onSuccess: invalidate,
  });
}

export function useDeleteSupplier() {
  const invalidate = useInvalidateSuppliers();
  return useMutation({
    mutationFn: supplierApi.remove,
    onSuccess: invalidate,
  });
}
