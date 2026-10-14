import type { BusinessUnit } from "@/modules/admin/organization/api";
export function reportUnitKind(unit?: Pick<BusinessUnit,"code"|"name">): string {
  const text = `${unit?.code || ""} ${unit?.name || ""}`.toUpperCase();
  return text.includes("HOTEL") ? "HOTEL" : text.includes("CATERING") ? "CATERING" : "CONSOLIDATED";
}
export function normalizeReportUnit<T extends {business_unit_id:string;report_scope:string}>(filters:T,units:BusinessUnit[]):T {
  if(filters.business_unit_id) return {...filters,report_scope:reportUnitKind(units.find(unit=>String(unit.id)===filters.business_unit_id))};
  const matches=units.filter(unit=>reportUnitKind(unit)===filters.report_scope);
  if(filters.report_scope!=="CONSOLIDATED"&&matches.length===1)return {...filters,business_unit_id:String(matches[0].id)};
  return {...filters,report_scope:"CONSOLIDATED"};
}
