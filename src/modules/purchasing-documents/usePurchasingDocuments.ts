import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { purchasingDocumentApi } from "./purchasingDocumentApi";
import type {
  PurchasingDocumentFilters,
  PurchasingDocumentPayload,
} from "./types";

export const purchasingDocumentKeys = {
  all: ["purchasing-documents"] as const,
  list: (filters: PurchasingDocumentFilters) =>
    [...purchasingDocumentKeys.all, "list", filters] as const,
  detail: (id: number) =>
    [...purchasingDocumentKeys.all, "detail", id] as const,
  summary: (filters: Omit<PurchasingDocumentFilters, "page" | "page_size">) =>
    [...purchasingDocumentKeys.all, "summary", filters] as const,
};

export function usePurchasingDocuments(filters: PurchasingDocumentFilters) {
  return useQuery({
    queryKey: purchasingDocumentKeys.list(filters),
    queryFn: async () => (await purchasingDocumentApi.list(filters)).data,
  });
}

export function usePurchasingDocument(id?: number) {
  return useQuery({
    queryKey: purchasingDocumentKeys.detail(id ?? 0),
    queryFn: async () => (await purchasingDocumentApi.detail(id as number)).data,
    enabled: id !== undefined,
  });
}

export function usePurchasingDocumentSummary(
  filters: Omit<PurchasingDocumentFilters, "page" | "page_size">,
) {
  return useQuery({
    queryKey: purchasingDocumentKeys.summary(filters),
    queryFn: async () => (await purchasingDocumentApi.summary(filters)).data,
  });
}

function useInvalidateDocuments() {
  const queryClient = useQueryClient();
  return () =>
    queryClient.invalidateQueries({ queryKey: purchasingDocumentKeys.all });
}

export function useCreatePurchasingDocument() {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: (payload: PurchasingDocumentPayload) =>
      purchasingDocumentApi.create(payload),
    onSuccess: invalidate,
  });
}

export function useUpdatePurchasingDocument() {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: Partial<PurchasingDocumentPayload>;
    }) => purchasingDocumentApi.update(id, payload),
    onSuccess: invalidate,
  });
}

export function useSetPurchasingDocumentActive() {
  const invalidate = useInvalidateDocuments();
  return useMutation({
    mutationFn: ({ id, active }: { id: number; active: boolean }) =>
      active
        ? purchasingDocumentApi.restore(id)
        : purchasingDocumentApi.archive(id),
    onSuccess: invalidate,
  });
}
