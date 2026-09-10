import { useQuery } from "@tanstack/react-query";
import { userApi } from "./userApi";

export const userKeys = {
  all: ["users"] as const,
  list: (params?: object) => [...userKeys.all, "list", params ?? {}] as const,
  detail: (userId: number) => [...userKeys.all, "detail", userId] as const,
  roles: () => [...userKeys.all, "roles"] as const,
  departments: () => [...userKeys.all, "departments"] as const,
  locations: () => [...userKeys.all, "locations"] as const,
  sessions: () => [...userKeys.all, "sessions"] as const,
};

export function useUsers(params: { page?: number; page_size?: number; search?: string } = {}) {
  return useQuery({
    queryKey: userKeys.list(params),
    queryFn: () => userApi.list(params),
    placeholderData: (previousData) => previousData,
  });
}

export function useUserDetail(userId: number | null) {
  return useQuery({
    queryKey: userKeys.detail(userId ?? 0),
    queryFn: () => userApi.detail(userId!),
    enabled: userId !== null,
  });
}

export function useAssignableRoles(enabled: boolean) {
  return useQuery({
    queryKey: userKeys.roles(),
    queryFn: userApi.roles,
    enabled,
  });
}

export function useAssignableDepartments(enabled: boolean) {
  return useQuery({
    queryKey: userKeys.departments(),
    queryFn: userApi.departments,
    enabled,
  });
}

export function useAssignableLocations(enabled: boolean) {
  return useQuery({
    queryKey: userKeys.locations(),
    queryFn: userApi.locations,
    enabled,
  });
}

export function useActiveSessions() {
  return useQuery({
    queryKey: userKeys.sessions(),
    queryFn: userApi.sessions,
  });
}
