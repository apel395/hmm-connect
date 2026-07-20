import api from "../../api/client";
import type { LoginRequest, TokenResponse, UserResponse } from "../../types/auth";

export async function login(
  credentials: LoginRequest,
): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>(
    "/auth/login",
    credentials,
  );

  return response.data;
}

export async function getCurrentUser(): Promise<UserResponse> {
  const response = await api.get<UserResponse>("/auth/me");
  return response.data;
}
