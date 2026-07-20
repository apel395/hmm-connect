import api from "../../api/client";

export interface Role {
  id: number;
  name: string;
  description: string | null;
}

export interface Department {
  id: number;
  code: string;
  name: string;
}

export interface Location {
  id: number;
  code: string;
  name: string;
  location_type: string;
}

export interface User {
  id: number;
  username: string;
  email: string;
  full_name: string;
  is_active: boolean;
  department_id: number | null;
  department: Department | null;
  location_id: number | null;
  location: Location | null;
  roles: Role[];
}

export interface CreateUserRequest {
  username: string;
  email: string;
  full_name: string;
  password: string;
  department_id?: number;
  location_id?: number;
  role_id?: number;
}

export async function getUsers(): Promise<User[]> {
  const response = await api.get<User[]>("/users");
  return response.data;
}

export async function createUser(
  data: CreateUserRequest,
): Promise<User> {
  const response = await api.post<User>("/users", data);
  return response.data;
}

export async function assignRole(userId: number, roleId: number): Promise<User> {
  const response = await api.post<User>(`/users/${userId}/roles`, { role_id: roleId });
  return response.data;
}

export async function removeRole(userId: number, roleId: number): Promise<User> {
  const response = await api.delete<User>(`/users/${userId}/roles/${roleId}`);
  return response.data;
}

export async function assignDepartment(
  userId: number,
  departmentId: number | null,
): Promise<User> {
  const response = await api.patch<User>(
    `/users/${userId}/department`,
    { department_id: departmentId },
  );
  return response.data;
}

export async function assignLocation(
  userId: number,
  locationId: number | null,
): Promise<User> {
  const response = await api.patch<User>(
    `/users/${userId}/location`,
    { location_id: locationId },
  );
  return response.data;
}
