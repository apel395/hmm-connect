import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  purchaseOrderApi,
  type PurchaseOrderCreatePayload,
} from "../api/purchaseOrderApi";



export function usePurchaseOrders(
  scope = "active"
) {

  return useQuery({

    queryKey: [
      "purchase-orders",
      scope,
    ],

    queryFn: async () => {

      const res =
        await purchaseOrderApi.list(
          scope
        );

      return res.data;

    },

  });

}



export function usePurchaseOrder(
  id: number
) {

  return useQuery({

    queryKey: [
      "purchase-order",
      id,
    ],

    queryFn: async () => {

      const res =
        await purchaseOrderApi.detail(
          id
        );

      return res.data;

    },

    enabled: !!id,

  });

}



/*
  Approved PR list for PO creation.

  Backend flow:

  PR
    ↓
  Approval
    ↓
  APPROVED
    ↓
  Create PO
*/

export function useApprovedPurchaseRequisitions() {

  return useQuery({

    queryKey: [
      "approved-purchase-requisitions",
    ],

    queryFn: async () => {

      const res =
        await purchaseOrderApi.approvedPurchaseRequisitions();

      return res.data;

    },

  });

}



export function useCreatePurchaseOrder() {

  const queryClient =
    useQueryClient();

  return useMutation({

    mutationFn: (
      payload: PurchaseOrderCreatePayload
    ) =>
      purchaseOrderApi.create(
        payload
      ),

    onSuccess: () => {

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-orders",
        ],

      });

      queryClient.invalidateQueries({

        queryKey: [
          "approved-purchase-requisitions",
        ],

      });

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-requisitions",
        ],

      });

    },

  });

}



export function useUpdatePurchaseOrder() {

  const queryClient =
    useQueryClient();

  return useMutation({

    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: PurchaseOrderCreatePayload;
    }) =>
      purchaseOrderApi.update(
        id,
        payload
      ),

    onSuccess: (
      _,
      variables
    ) => {

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-orders",
        ],

      });

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-order",
          variables.id,
        ],

      });

    },

  });

}



export function useSubmitPurchaseOrder() {

  const queryClient =
    useQueryClient();

  return useMutation({

    mutationFn: (
      id: number
    ) =>
      purchaseOrderApi.submit(
        id
      ),

    onSuccess: () => {

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-orders",
        ],

      });

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-order",
        ],

      });

      queryClient.invalidateQueries({

        queryKey: [
          "approval",
        ],

      });

    },

  });

}



export function useApprovePurchaseOrder() {

  const queryClient =
    useQueryClient();

  return useMutation({

    mutationFn: ({
      id,
      comment,
    }: {
      id: number;
      comment?: string;
    }) =>
      purchaseOrderApi.approve(
        id,
        comment
      ),

    onSuccess: () => {

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-orders",
        ],

      });

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-order",
        ],

      });

      queryClient.invalidateQueries({

        queryKey: [
          "approval",
        ],

      });

    },

  });

}



export function useRejectPurchaseOrder() {

  const queryClient =
    useQueryClient();

  return useMutation({

    mutationFn: ({
      id,
      comment,
    }: {
      id: number;
      comment?: string;
    }) =>
      purchaseOrderApi.reject(
        id,
        comment
      ),

    onSuccess: () => {

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-orders",
        ],

      });

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-order",
        ],

      });

      queryClient.invalidateQueries({

        queryKey: [
          "approval",
        ],

      });

    },

  });

}



export function useCancelPurchaseOrder() {

  const queryClient =
    useQueryClient();

  return useMutation({

    mutationFn: (
      id: number
    ) =>
      purchaseOrderApi.cancel(
        id
      ),

    onSuccess: () => {

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-orders",
        ],

      });

      queryClient.invalidateQueries({

        queryKey: [
          "purchase-order",
        ],

      });

    },

  });

}