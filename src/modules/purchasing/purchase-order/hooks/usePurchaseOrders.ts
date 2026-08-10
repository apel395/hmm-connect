import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { purchaseOrderApi, type PurchaseOrderCreatePayload } from "../api/purchaseOrderApi";

const invalidatePO = (queryClient: ReturnType<typeof useQueryClient>, id?: number) => {
  queryClient.invalidateQueries({ queryKey: ["purchase-orders"] });
  queryClient.invalidateQueries({ queryKey: ["purchase-order"] });
  if (id) queryClient.invalidateQueries({ queryKey: ["purchase-order", id] });
  queryClient.invalidateQueries({ queryKey: ["approval"] });
};

export function usePurchaseOrders(scope: "active" | "history" | "all" = "all", page = 1, pageSize = 20, status?: string) {
  return useQuery({
    queryKey: ["purchase-orders", scope, page, pageSize, status],
    queryFn: async () => (await purchaseOrderApi.list({ scope, page, page_size: pageSize, status })).data,
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
    onSuccess: () => {
      invalidatePO(queryClient);
      queryClient.invalidateQueries({ queryKey: ["approved-purchase-requisitions"] });
      queryClient.invalidateQueries({ queryKey: ["purchase-requisitions"] });
    },
  });
}

export function useUpdatePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: PurchaseOrderCreatePayload }) => purchaseOrderApi.update(id, payload),
    onSuccess: (_, variables) => invalidatePO(queryClient, variables.id),
  });
}

export function useReopenPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => purchaseOrderApi.reopen(id),
    onSuccess: (_, id) => invalidatePO(queryClient, id),
  });
}

export function useSubmitPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: (id: number) => purchaseOrderApi.submit(id), onSuccess: (_, id) => invalidatePO(queryClient, id) });
}

export function useApprovePurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, comment }: { id: number; comment?: string }) => purchaseOrderApi.approve(id, comment),
    onSuccess: (_, variables) => invalidatePO(queryClient, variables.id),
  });
}

export function useRejectPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, comment }: { id: number; comment?: string }) => purchaseOrderApi.reject(id, comment),
    onSuccess: (_, variables) => invalidatePO(queryClient, variables.id),
  });
}

export function useCancelPurchaseOrder() {
  const queryClient = useQueryClient();
  return useMutation({ mutationFn: (id: number) => purchaseOrderApi.cancel(id), onSuccess: (_, id) => invalidatePO(queryClient, id) });
}
