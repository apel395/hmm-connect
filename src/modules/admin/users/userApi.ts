import api from "@/api/client";
import type { AdminUser } from "./types";

type UserListResponse =
  | AdminUser[]
  | { items?: AdminUser[] }
  | { data?: AdminUser[] };

export const userApi = {
  async list(): Promise<AdminUser[]> {
    const response = await api.get<UserListResponse>("/users");
    if (Array.isArray(response.data)) return response.data;
    if ("items" in response.data && Array.isArray(response.data.items)) {
      return response.data.items;
    }
    if ("data" in response.data && Array.isArray(response.data.data)) {
      return response.data.data;
    }
    return [];
  },
};
