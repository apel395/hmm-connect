import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";


import {
  supplierProductApi,
  type SupplierProductPayload,
} from "../api/supplierProductApi";



export function useSupplierProducts(
  supplierId?: number
) {

  return useQuery({

    queryKey: [
      "supplier-products",
      supplierId,
    ],


    queryFn: async () => {

      if (!supplierId) {
        return [];
      }


      const res =
        await supplierProductApi.list(
          supplierId
        );


      return res.data;

    },


    enabled:
      !!supplierId,

  });

}





export function useCreateSupplierProduct() {

  const qc =
    useQueryClient();


  return useMutation({

    mutationFn: ({
      supplierId,
      payload,
    }: {
      supplierId: number;

      payload: SupplierProductPayload;

    }) =>

      supplierProductApi.create(
        supplierId,
        payload
      ),



    onSuccess: (
      _,
      variables
    ) => {

      qc.invalidateQueries({

        queryKey: [
          "supplier-products",
          variables.supplierId,
        ],

      });

    },

  });

}






export function useDeleteSupplierProduct() {

  const qc =
    useQueryClient();


  return useMutation({

    mutationFn: ({
      supplierId,
      supplierProductId,
    }: {
      supplierId: number;

      supplierProductId: number;

    }) =>

      supplierProductApi.remove(
        supplierId,
        supplierProductId
      ),



    onSuccess: (
      _,
      variables
    ) => {

      qc.invalidateQueries({

        queryKey: [
          "supplier-products",
          variables.supplierId,
        ],

      });

    },

  });

}