import axios from "axios";

export interface RegistrationPayload {
  username: string;
  full_name: string;
  email: string;
  password: string;
}

export interface RegistrationResponse {
  id: number;
  username: string;
  full_name: string;
  email: string;
  is_active: boolean;
  requires_admin_access: boolean;
  message: string;
}

export function registerAccount(payload: RegistrationPayload) {
  const baseUrl = String(import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
  return axios.post<RegistrationResponse>(
    `${baseUrl}/auth/register`,
    payload,
    {
      timeout: 30_000,
      headers: { "Content-Type": "application/json" },
    },
  );
}
