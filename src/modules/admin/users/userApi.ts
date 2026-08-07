import api from "@/api/client";
import type {
  AdminUser,
  EditableUser,
  UserCreatePayload,
  UserDepartment,
  UserDetailsUpdate,
  UserLocation,
  UserRole,
} from "./types";

type UserListResponse = AdminUser[] | { items?: AdminUser[] } | { data?: AdminUser[] };

export const userApi = {
  async list(): Promise<AdminUser[]> {
    const response = await api.get<UserListResponse>("/users");
    if (Array.isArray(response.data)) return response.data;
    if ("items" in response.data && Array.isArray(response.data.items)) return response.data.items;
    if ("data" in response.data && Array.isArray(response.data.data)) return response.data.data;
    return [];
  },
  async create(data: UserCreatePayload): Promise<EditableUser> {
    return (await api.post<EditableUser>("/users", data)).data;
  },
  async detail(userId: number): Promise<EditableUser> {
    return (await api.get<EditableUser>(`/users/${userId}`)).data;
  },
  async roles(): Promise<UserRole[]> {
    return (await api.get<UserRole[]>("/users/roles")).data;
  },
  async departments(): Promise<UserDepartment[]> {
    return (await api.get<UserDepartment[]>("/users/departments")).data;
  },
  async locations(): Promise<UserLocation[]> {
    return (await api.get<UserLocation[]>("/users/locations")).data;
  },
  async update(userId: number, data: UserDetailsUpdate): Promise<EditableUser> {
    return (await api.patch<EditableUser>(`/users/${userId}`, data)).data;
  },
  async replaceRoles(userId: number, roleIds: number[]): Promise<EditableUser> {
    return (await api.put<EditableUser>(`/users/${userId}/roles`, { role_ids: roleIds })).data;
  },
  async remove(userId: number): Promise<void> {
    await api.delete(`/users/${userId}`);
  },
};
