import { useQuery } from "@tanstack/react-query";
import { userApi } from "./userApi";

export const userKeys = {
  all: ["users"] as const,
  list: () => [...userKeys.all, "list"] as const,
};

export function useUsers() {
  return useQuery({
    queryKey: userKeys.list(),
    queryFn: userApi.list,
  });
}
