import api from "../../api/client";

export interface Location {
  id: number;
  code: string;
  name: string;
  location_type: string;
  is_active: boolean;
}

export interface CreateLocationRequest {
  code: string;
  name: string;
  location_type: string;
}

export interface UpdateLocationRequest {
  name?: string;
  location_type?: string;
  is_active?: boolean;
}

export async function getLocations(): Promise<Location[]> {
  const response = await api.get<Location[]>("/locations");
  return response.data;
}

export async function createLocation(
  data: CreateLocationRequest,
): Promise<Location> {
  const response = await api.post<Location>("/locations", data);
  return response.data;
}

export async function updateLocation(
  locationId: number,
  data: UpdateLocationRequest,
): Promise<Location> {
  const response = await api.patch<Location>(
    `/locations/${locationId}`,
    data,
  );
  return response.data;
}
