import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { supplierApi, type SupplierListParams } from "../api/supplierApi";
import type { SupplierPayload } from "../types";

export const supplierKeys = {
  all: ["suppliers"] as const,
  lists: () => [...supplierKeys.all, "list"] as const,
  lookup: (search: string) => [...supplierKeys.all, "lookup", search] as const,
  detail: (id: number) => [...supplierKeys.all, "detail", id] as const,
};

// Backward-compatible form lookup. Master list pages should use useSupplierPage.
export function useSuppliers(search = "") {
  return useQuery({
    queryKey: supplierKeys.lookup(search),
    queryFn: () => supplierApi.lookup(search, 100),
    staleTime: 60_000,
  });
}

export function useSupplierPage(params: SupplierListParams = {}) {
  return useQuery({
    queryKey: [...supplierKeys.lists(), params],
    queryFn: () => supplierApi.list(params),
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
  return useMutation({ mutationFn: (payload: SupplierPayload) => supplierApi.create(payload), onSuccess: invalidate });
}

export function useUpdateSupplier() {
  const invalidate = useInvalidateSuppliers();
  return useMutation({ mutationFn: ({ id, payload }: { id: number; payload: SupplierPayload }) => supplierApi.update(id, payload), onSuccess: invalidate });
}

export function useDeleteSupplier() {
  const invalidate = useInvalidateSuppliers();
  return useMutation({ mutationFn: supplierApi.remove, onSuccess: invalidate });
}
