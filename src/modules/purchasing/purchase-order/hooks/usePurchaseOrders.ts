import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { purchaseOrderApi, type PurchaseOrderCreatePayload } from "../api/purchaseOrderApi";

async function invalidatePO(queryClient: ReturnType<typeof useQueryClient>, id?: number, detail?: unknown) {
  if (id && detail) {
    queryClient.setQueryData(["purchase-order", id], detail);
    // The mutation response is produced after the backend commit and is the
    // authoritative state for the currently mounted detail page. Mark it stale
    // for the next mount, but do not immediately overwrite it with a GET that
    // may still be served from an older edge/cache snapshot.
    await queryClient.invalidateQueries({
      queryKey: ["purchase-order", id],
      exact: true,
      refetchType: "none",
    });
  }
  await Promise.all([
    queryClient.invalidateQueries({ queryKey: ["purchase-orders"] }),
    queryClient.invalidateQueries({ queryKey: ["approval"] }),
    queryClient.invalidateQueries({ queryKey: ["approval-inbox"] }),
  ]);
}

export function usePurchaseOrders(scope: "active" | "history" | "all" = "all", page = 1, pageSize = 20, status?: string, search?: string) {
  return useQuery({
    queryKey: ["purchase-orders", scope, page, pageSize, status, search],
    queryFn: async () => (await purchaseOrderApi.list({ scope, page, page_size: pageSize, status, search: search?.trim() || undefined })).data,
    placeholderData: (previous) => previous,
  });
}

export function usePurchaseOrder(id: number) {
  return useQuery({
    queryKey: ["purchase-order", id],
    queryFn: async () => (await purchaseOrderApi.detail(id)).data,
    enabled: !!id,
  });
}

export function useApprovedPurchaseRequisitions() {
  return useQuery({
    queryKey: ["approved-purchase-requisitions"],
    queryFn: async () => (await purchaseOrderApi.approvedPurchaseRequisitions()).data,
  });
}

export function useCreatePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PurchaseOrderCreatePayload) => purchaseOrderApi.create(payload),
    onSuccess: async () => {
      await invalidatePO(queryClient);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["approved-purchase-requisitions"] }),
        queryClient.invalidateQueries({ queryKey: ["purchase-requisitions"] }),
      ]);
    },
  });
}

export function useUpdatePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: PurchaseOrderCreatePayload }) => purchaseOrderApi.update(id, payload),
    onSuccess: (response, variables) => invalidatePO(queryClient, variables.id, response.data),
  });
}

export function useReopenPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => purchaseOrderApi.reopen(id),
    onSuccess: (response, id) => invalidatePO(queryClient, id, response.data),
  });
}

export function useSubmitPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: (id: number) => purchaseOrderApi.submit(id), onSuccess: (response, id) => invalidatePO(queryClient, id, response.data) });
}

export function useApprovePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, comment }: { id: number; comment?: string }) => purchaseOrderApi.approve(id, comment),
    onSuccess: (response, variables) => invalidatePO(queryClient, variables.id, response.data),
  });
}

export function useRejectPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, comment }: { id: number; comment?: string }) => purchaseOrderApi.reject(id, comment),
    onSuccess: (response, variables) => invalidatePO(queryClient, variables.id, response.data),
  });
}

export function useCancelPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: (id: number) => purchaseOrderApi.cancel(id), onSuccess: (response, id) => invalidatePO(queryClient, id, response.data) });
}
