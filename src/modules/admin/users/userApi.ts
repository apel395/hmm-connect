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

export type UserListPage = {
  items: AdminUser[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type ActiveSessionInfo = {
  id: number;
  username: string;
  full_name: string;
  email: string;
  is_active: boolean;
  department?: { id: number; code: string; name: string } | null;
  location?: { id: number; code: string; name: string } | null;
  roles: { id: number; name: string }[];
  session_id: string;
  session_last_activity_at: string | null;
  idle_seconds: number | null;
  is_idle: boolean;
};

export type ActiveSessionsResponse = {
  items: ActiveSessionInfo[];
  total_active_sessions: number;
};

export const userApi = {
  async list(params: { page?: number; page_size?: number; search?: string; is_active?: boolean } = {}): Promise<UserListPage> {
    return (await api.get<UserListPage>("/users", { params })).data;
  },
  async sessions(): Promise<ActiveSessionsResponse> {
    return (await api.get<ActiveSessionsResponse>("/users/sessions")).data;
  },
  async clearSession(userId: number): Promise<void> {
    await api.post(`/users/${userId}/clear-session`);
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
