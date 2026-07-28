import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  requisitionApi,
} from "../api/requisitionApi";

export function usePurchaseRequisitions() {

  return useQuery({

    queryKey: [
      "purchase-requisitions",
    ],

    queryFn: async () => {

      const res =
        await requisitionApi.list();

      return res.data;

    },

  });

}

export function usePurchaseRequisition(
  id: number,
) {

  return useQuery({

    queryKey: [
      "purchase-requisition",
      id,
    ],

    queryFn: async () => {

      const res =
        await requisitionApi.detail(
          id,
        );

      return res.data;

    },

    enabled: !!id,

  });

}

export function usePurchaseRequisitionTraceability(
  id: number,
) {

  return useQuery({

    queryKey: [
      "purchase-requisition-traceability",
      id,
    ],

    queryFn: async () => {

      const res =
        await requisitionApi.traceability(
          id,
        );

      return res.data;

    },

    enabled: !!id,

  });

}

export function useCreatePurchaseRequisition() {

  const qc =
    useQueryClient();

  return useMutation({

    mutationFn: async (
      payload: any,
    ) => {

      const res =
        await requisitionApi.create(
          payload,
        );

      return res.data;

    },

    onSuccess() {

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisitions",
        ],

      });

    },

  });

}

export function useUpdatePurchaseRequisition() {

  const qc =
    useQueryClient();

  return useMutation({

    mutationFn: (
      payload: {
        id: number;
        data: any;
      },
    ) =>

      requisitionApi.update(
        payload.id,
        payload.data,
      ),

    onSuccess: (
      _,
      variables,
    ) => {

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisitions",
        ],

      });

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisition",
          variables.id,
        ],

      });

    },

  });

}

export function useSubmitPurchaseRequisition() {

  const qc =
    useQueryClient();

  return useMutation({

    mutationFn: (
      id: number,
    ) =>

      requisitionApi.submit(
        id,
      ),

    onSuccess: (
      _,
      id,
    ) => {

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisitions",
        ],

      });

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisition",
          id,
        ],

      });

      qc.invalidateQueries({

        queryKey: [
          "approval",
          "PURCHASE_REQUISITION",
          id,
        ],

      });

    },

  });

}

export function useApprovePurchaseRequisition() {

  const qc =
    useQueryClient();

  return useMutation({

    mutationFn: (
      payload: {
        id: number;
        comment?: string;
      },
    ) =>

      requisitionApi.approve(
        payload.id,
        payload.comment,
      ),

    onSuccess: (
      _,
      variables,
    ) => {

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisitions",
        ],

      });

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisition",
          variables.id,
        ],

      });

      qc.invalidateQueries({

        queryKey: [
          "approval",
          "PURCHASE_REQUISITION",
          variables.id,
        ],

      });

    },

  });

}

export function useRejectPurchaseRequisition() {

  const qc =
    useQueryClient();

  return useMutation({

    mutationFn: (
      payload: {
        id: number;
        comment?: string;
      },
    ) =>

      requisitionApi.reject(
        payload.id,
        payload.comment,
      ),

    onSuccess: (
      _,
      variables,
    ) => {

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisitions",
        ],

      });

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisition",
          variables.id,
        ],

      });

      qc.invalidateQueries({

        queryKey: [
          "approval",
          "PURCHASE_REQUISITION",
          variables.id,
        ],

      });

    },

  });

}

export function useCancelPurchaseRequisition() {

  const qc =
    useQueryClient();

  return useMutation({

    mutationFn: (
      id: number,
    ) =>

      requisitionApi.cancel(
        id,
      ),

    onSuccess: (
      _,
      id,
    ) => {

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisitions",
        ],

      });

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisition",
          id,
        ],

      });

    },

  });

}

export function useConvertPurchaseRequisition() {

  const qc =
    useQueryClient();

  return useMutation({

    mutationFn: (
      payload: {
        id: number;
        supplier_id: number;
      },
    ) =>

      requisitionApi.convertToPO(
        payload.id,
        payload.supplier_id,
      ),

    onSuccess: () => {

      qc.invalidateQueries({

        queryKey: [
          "purchase-requisitions",
        ],

      });

    },

  });

}