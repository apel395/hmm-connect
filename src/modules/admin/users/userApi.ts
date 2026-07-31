import api from "@/api/client";
import type {
  AdminUser,
  EditableUser,
  UserDepartment,
  UserDetailsUpdate,
  UserLocation,
  UserRole,
} from "./types";

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
  async detail(userId: number): Promise<EditableUser> {
    const response = await api.get<EditableUser>(`/users/${userId}`);
    return response.data;
  },
  async roles(): Promise<UserRole[]> {
    const response = await api.get<UserRole[]>("/users/roles");
    return response.data;
  },
  async departments(): Promise<UserDepartment[]> {
    const response = await api.get<UserDepartment[]>("/users/departments");
    return response.data;
  },
  async locations(): Promise<UserLocation[]> {
    const response = await api.get<UserLocation[]>("/users/locations");
    return response.data;
  },
  async update(userId: number, data: UserDetailsUpdate): Promise<EditableUser> {
    const response = await api.patch<EditableUser>(`/users/${userId}`, data);
    return response.data;
  },
  async replaceRoles(userId: number, roleIds: number[]): Promise<EditableUser> {
    const response = await api.put<EditableUser>(`/users/${userId}/roles`, {
      role_ids: roleIds,
    });
    return response.data;
  },
};
