import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { requisitionApi } from "../api/requisitionApi";

function refresh(qc: ReturnType<typeof useQueryClient>, id?: number) {
  qc.invalidateQueries({ queryKey: ["purchase-requisitions"] });
  qc.invalidateQueries({ queryKey: ["purchase-requisition"] });
  if (id) {
    qc.invalidateQueries({ queryKey: ["purchase-requisition", id] });
    qc.invalidateQueries({ queryKey: ["approval", "PURCHASE_REQUISITION", id] });
  }
}

export function usePurchaseRequisitions(scope = "active") {
  return useQuery({ queryKey: ["purchase-requisitions", scope], queryFn: async () => (await requisitionApi.list(scope)).data });
}

export function usePurchaseRequisition(id: number) {
  return useQuery({ queryKey: ["purchase-requisition", id], queryFn: async () => (await requisitionApi.detail(id)).data, enabled: !!id });
}

export function usePurchaseRequisitionTraceability(id: number) {
  return useQuery({ queryKey: ["purchase-requisition-traceability", id], queryFn: async () => (await requisitionApi.traceability(id)).data, enabled: !!id });
}

export function useCreatePurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: async (payload: any) => (await requisitionApi.create(payload)).data, onSuccess: () => refresh(qc) });
}

export function useUpdatePurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: ({ id, data }: { id: number; data: any }) => requisitionApi.update(id, data), onSuccess: (_, variables) => refresh(qc, variables.id) });
}

export function useReopenPurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: number) => requisitionApi.reopen(id), onSuccess: (_, id) => refresh(qc, id) });
}

export function useSubmitPurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: number) => requisitionApi.submit(id), onSuccess: (_, id) => refresh(qc, id) });
}

export function useApprovePurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: ({ id, comment }: { id: number; comment?: string }) => requisitionApi.approve(id, comment), onSuccess: (_, variables) => refresh(qc, variables.id) });
}

export function useRejectPurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: ({ id, comment }: { id: number; comment?: string }) => requisitionApi.reject(id, comment), onSuccess: (_, variables) => refresh(qc, variables.id) });
}

export function useCancelPurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: number) => requisitionApi.cancel(id), onSuccess: (_, id) => refresh(qc, id) });
}

export function useConvertPurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: ({ id, supplier_id }: { id: number; supplier_id: number }) => requisitionApi.convertToPO(id, supplier_id), onSuccess: () => refresh(qc) });
}
