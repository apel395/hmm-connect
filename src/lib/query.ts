import { isMasterDataQuery, subscribeMasterDataChange } from "./masterDataEvents";
import { QueryClient } from "@tanstack/react-query";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 60 * 1000,
    },
    mutations: {
      retry: 0,
    },
  },
});

subscribeMasterDataChange(kind => {
  void queryClient.invalidateQueries({ predicate: query => isMasterDataQuery(query.queryKey, kind) });
});
export default queryClient;
