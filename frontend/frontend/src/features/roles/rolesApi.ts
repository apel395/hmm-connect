import api from "../../api/client";

export interface Role {
  id: number;
  name: string;
  description: string | null;
}

export interface CreateRoleRequest {
  name: string;
  description?: string;
}

export interface UpdateRoleRequest {
  name?: string;
  description?: string;
}

export async function getRoles(): Promise<Role[]> {
  const response = await api.get<Role[]>("/roles");
  return response.data;
}

export async function createRole(
  data: CreateRoleRequest,
): Promise<Role> {
  const response = await api.post<Role>("/roles", data);
  return response.data;
}

export async function updateRole(
  roleId: number,
  data: UpdateRoleRequest,
): Promise<Role> {
  const response = await api.patch<Role>(`/roles/${roleId}`, data);
  return response.data;
}

export async function deleteRole(roleId: number): Promise<void> {
  await api.delete(`/roles/${roleId}`);
}
