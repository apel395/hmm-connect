import { useMutation, useQuery } from "@tanstack/react-query";
import { getCurrentUser, login } from "./authApi";
import type { LoginRequest } from "../../types/auth";

export function useLogin() {
  return useMutation({
    mutationFn: (credentials: LoginRequest) => login(credentials),

    onSuccess: (data) => {
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
    },
  });
}

export function useCurrentUser() {
  return useQuery({
    queryKey: ["current-user"],
    queryFn: getCurrentUser,
    enabled: Boolean(localStorage.getItem("access_token")),
    retry: false,
  });
}

export function logout() {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  window.location.href = "/login";
}
