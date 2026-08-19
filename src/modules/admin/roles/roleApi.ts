import api from "@/api/client";

export type ManagedPermission = { id: number; code: string; description?: string | null };
export type ManagedRole = { id: number; name: string; description?: string | null; permissions: ManagedPermission[]; user_count: number };
export type RolePayload = { name: string; description?: string | null; permission_codes: string[] };

export const roleApi = {
  list: async () => (await api.get<ManagedRole[]>("/roles")).data,
  permissions: async () => (await api.get<ManagedPermission[]>("/roles/permissions")).data,
  create: async (payload: RolePayload) => (await api.post<ManagedRole>("/roles", payload)).data,
  update: async (id: number, payload: RolePayload) => (await api.patch<ManagedRole>(`/roles/${id}`, payload)).data,
  remove: async (id: number) => api.delete(`/roles/${id}`),
};
