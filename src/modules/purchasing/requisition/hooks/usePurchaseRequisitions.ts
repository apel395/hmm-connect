import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { requisitionApi, type RequisitionListParams } from "../api/requisitionApi";

async function refresh(qc: ReturnType<typeof useQueryClient>, id?: number, detail?: unknown) {
  if (id && detail) qc.setQueryData(["purchase-requisition", id], detail);
  await Promise.all([
    qc.invalidateQueries({ queryKey: ["purchase-requisitions"] }),
    id ? qc.refetchQueries({ queryKey: ["purchase-requisition", id], exact: true, type: "active" }) : Promise.resolve(),
    id ? qc.refetchQueries({ queryKey: ["approval", "PURCHASE_REQUISITION", id], exact: true, type: "active" }) : Promise.resolve(),
    qc.invalidateQueries({ queryKey: ["approval-inbox"] }),
  ]);
}

export function usePurchaseRequisitions(params: RequisitionListParams = { scope: "active" }) {
  return useQuery({
    queryKey: ["purchase-requisitions", params],
    queryFn: async () => (await requisitionApi.list(params)).data,
    placeholderData: (previous) => previous,
  });
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
  return useMutation({ mutationFn: ({ id, data }: { id: number; data: any }) => requisitionApi.update(id, data), onSuccess: (response, variables) => refresh(qc, variables.id, response.data) });
}

export function useReopenPurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: number) => requisitionApi.reopen(id), onSuccess: (response, id) => refresh(qc, id, response.data) });
}

export function useSubmitPurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: number) => requisitionApi.submit(id), onSuccess: (response, id) => refresh(qc, id, response.data) });
}

export function useApprovePurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: ({ id, comment }: { id: number; comment?: string }) => requisitionApi.approve(id, comment), onSuccess: (response, variables) => refresh(qc, variables.id, response.data) });
}

export function useRejectPurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: ({ id, comment }: { id: number; comment?: string }) => requisitionApi.reject(id, comment), onSuccess: (response, variables) => refresh(qc, variables.id, response.data) });
}

export function useCancelPurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: (id: number) => requisitionApi.cancel(id), onSuccess: (response, id) => refresh(qc, id, response.data) });
}

export function useConvertPurchaseRequisition() {
  const qc = useQueryClient();
  return useMutation({ mutationFn: ({ id, supplier_id }: { id: number; supplier_id: number }) => requisitionApi.convertToPO(id, supplier_id), onSuccess: () => refresh(qc) });
}
