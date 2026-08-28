import api from "@/api/client";

export interface BusinessUnit {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface Department {
  id: number;
  code: string;
  name: string;
  business_unit_id?: number | null;
  business_unit_name?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
}

export interface Location extends Department {
  business_unit_id: number;
  location_type: string;
  address?: string | null;
  city?: string | null;
  province?: string | null;
  postal_code?: string | null;
}

export type OrganizationRecord = BusinessUnit | Department | Location;
export interface OrganizationPayload {
  code: string; name: string; description?: string | null; business_unit_id?: number | null;
  location_type?: string; address?: string | null; city?: string | null; province?: string | null;
  postal_code?: string | null; is_active?: boolean;
}
export interface OrganizationFilters { business_unit_id?: number; location_id?: number; location_type?: string; is_active?: boolean; search?: string; assigned_only?: boolean }

export const listBusinessUnits = async () =>
  (await api.get<BusinessUnit[]>("/business-units")).data;
export const filterBusinessUnits = async (filters: Omit<OrganizationFilters, "business_unit_id"> = {}) =>
  (await api.get<BusinessUnit[]>("/business-units", { params: filters })).data;
export const createBusinessUnit = async (payload: OrganizationPayload) =>
  (await api.post<BusinessUnit>("/business-units", payload)).data;
export const updateBusinessUnit = async (id: number, payload: Partial<OrganizationPayload>) =>
  (await api.patch<BusinessUnit>(`/business-units/${id}`, payload)).data;

export const listDepartments = async (filtersOrBusinessUnit: OrganizationFilters | number = {}) =>
  (await api.get<Department[]>("/departments", { params: typeof filtersOrBusinessUnit === "number" ? { business_unit_id: filtersOrBusinessUnit } : filtersOrBusinessUnit })).data;
export const createDepartment = async (payload: OrganizationPayload) =>
  (await api.post<Department>("/departments", payload)).data;
export const updateDepartment = async (id: number, payload: Partial<OrganizationPayload>) =>
  (await api.patch<Department>(`/departments/${id}`, payload)).data;
export const deactivateDepartment = async (id: number) =>
  (await api.delete<Department>(`/departments/${id}`)).data;

export const listLocations = async (filtersOrBusinessUnit: OrganizationFilters | number = {}) => {
  const params =
    typeof filtersOrBusinessUnit === "number"
      ? { business_unit_id: filtersOrBusinessUnit, assigned_only: true }
      : { assigned_only: true, ...filtersOrBusinessUnit };
  return (await api.get<Location[]>("/locations", { params })).data;
};
export const createLocation = async (payload: OrganizationPayload) =>
  (await api.post<Location>("/locations", payload)).data;
export const updateLocation = async (id: number, payload: Partial<OrganizationPayload>) =>
  (await api.patch<Location>(`/locations/${id}`, payload)).data;
export const deactivateLocation = async (id: number) =>
  (await api.delete<Location>(`/locations/${id}`)).data;
