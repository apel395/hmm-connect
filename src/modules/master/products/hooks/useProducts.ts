import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import { productApi, type ProductListParams } from "../api/productApi";

export function useProducts(params: ProductListParams = {}) {
  return useQuery({
    queryKey: ["products", params],
    queryFn: async () => {
      const res = await productApi.list(params);
      return res.data;
    },
  });
}

export function useProductLookup(search = "", limit = 30) {
  return useQuery({
    queryKey: ["products", "lookup", search, limit],
    queryFn: async () => {
      const res = await productApi.lookup(search, limit);
      return res.data;
    },
    staleTime: 60_000,
  });
}

export function useCreateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: any) => productApi.create(payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useUpdateProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: any }) => productApi.update(id, payload),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}

export function useDeleteProduct() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => productApi.remove(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["products"] }),
  });
}