export interface UserPermission {
  id: number;
  code: string;
  description?: string | null;
}

export interface UserRole {
  id: number;
  name: string;
  description?: string | null;
  permissions?: UserPermission[];
}

export interface UserDepartment {
  id: number;
  code: string;
  name: string;
}

export interface UserLocation {
  id: number;
  code: string;
  name: string;
  location_type: string;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string;
  full_name: string;
  is_active: boolean;
  department_id?: number | null;
  location_id?: number | null;
  department?: UserDepartment | null;
  location?: UserLocation | null;
  roles: UserRole[];
  created_at: string;
  updated_at: string;
}

export interface EditableUser extends AdminUser {
  role_ids: number[];
}

export interface UserCreatePayload {
  username: string;
  email: string;
  full_name: string;
  password: string;
  is_active?: boolean;
  department_id?: number | null;
  location_id?: number | null;
  role_ids: number[];
}

export interface UserDetailsUpdate {
  password?: string;
  username?: string;
  email?: string;
  full_name?: string;
  is_active?: boolean;
  department_id?: number | null;
  location_id?: number | null;
}
