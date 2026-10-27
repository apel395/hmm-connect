type Location = { id: number; catalog_type?: string; name: string; has_outlets?: boolean };
type Department = { id: number; location_id: number; is_outlet?: boolean; is_fnb_outlet?: boolean; code?: string; name: string; display_name?: string };
export type PosContextOptions = { locations?: Location[]; departments?: Department[] };

/** URL/filter IDs are untrusted input; only resolved, accessible Hotel children are contexts. */
export function hotelOutletContext(options: PosContextOptions | undefined, locationId?: number, departmentId?: number) {
  const locations = (options?.locations ?? []).filter(row => row.catalog_type === "HOTEL");
  const location = locations.find(row => row.id === locationId);
  const departments = (options?.departments ?? []).filter(row => Boolean(location) && row.location_id === location!.id && row.is_outlet && row.is_fnb_outlet);
  const department = departments.find(row => row.id === departmentId);
  const valid = Boolean(location && department);
  const invalidLink = Boolean(options && ((locationId && !location) || (departmentId && !department)));
  return { locations, departments, location, department, valid, invalidLink,
    href: valid ? `/pos/operations?location=${location!.id}&outlet=${department!.id}` : "/pos/operations" };
}
