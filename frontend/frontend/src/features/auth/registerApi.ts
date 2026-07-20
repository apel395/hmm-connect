import api from "../../api/client";

export interface RegisterRequest {
  username: string;
  email: string;
  full_name: string;
  password: string;
}

export interface UserResponse {
  id: number;
  username: string;
  email: string;
  full_name: string;
}

export async function register(
  data: RegisterRequest,
): Promise<UserResponse> {
  const response = await api.post<UserResponse>(
    "/auth/register",
    data,
  );

  return response.data;
}