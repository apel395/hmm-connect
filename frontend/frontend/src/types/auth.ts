export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RoleResponse {
  id: number;
  name: string;
  description: string | null;
}

export interface DepartmentResponse {
  id: number;
  code: string;
  name: string;
}

export interface LocationResponse {
  id: number;
  code: string;
  name: string;
  location_type: string;
}

export interface UserResponse {
  id: number;
  username: string;
  email: string;
  full_name: string;
  is_active: boolean;
  department_id: number | null;
  department: DepartmentResponse | null;
  location_id: number | null;
  location: LocationResponse | null;
  roles: RoleResponse[];
}
