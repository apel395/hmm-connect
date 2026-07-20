import api from "../../api/client";

export interface Department {
  id: number;
  code: string;
  name: string;
  is_active: boolean;
}

export async function getDepartments(): Promise<Department[]> {
  const response = await api.get<Department[]>("/departments");
  return response.data;
}
