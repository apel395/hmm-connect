import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  productApi,
} from "../api/productApi";

export function useProducts() {
  return useQuery({
    queryKey: ["products"],

    queryFn: async () => {
      const res =
        await productApi.list();

      return res.data;
    },
  });
}

export function useCreateProduct() {
  const queryClient =
    useQueryClient();

  return useMutation({
    mutationFn: (
      payload: any
    ) =>
      productApi.create(
        payload
      ),

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "products",
        ],
      });
    },
  });
}

export function useUpdateProduct() {
  const queryClient =
    useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      payload,
    }: {
      id: number;
      payload: any;
    }) =>
      productApi.update(
        id,
        payload
      ),

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "products",
        ],
      });
    },
  });
}

export function useDeleteProduct() {
  const queryClient =
    useQueryClient();

  return useMutation({
    mutationFn: (
      id: number
    ) =>
      productApi.remove(
        id
      ),

    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: [
          "products",
        ],
      });
    },
  });
}