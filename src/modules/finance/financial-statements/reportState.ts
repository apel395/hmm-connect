import { browserDraftStorage, draftKey, readDraft, writeDraft } from "@/utils/formDraftStorage";

export type ReportFilters = { as_of_date: string; business_unit_id: string; location_id: string; department_id: string; budget_id: string; kap: boolean; include_zero: boolean; report_scope: string };
export type ReportPreferences = { filters: ReportFilters; period: "MTD" | "YTD"; view: "DETAIL" | "EXECUTIVE" };
const valid = (value: unknown): value is ReportPreferences => {
  if (!value || typeof value !== "object") return false;
  const entry = value as ReportPreferences;
  return ["MTD", "YTD"].includes(entry.period) && ["DETAIL", "EXECUTIVE"].includes(entry.view) && !!entry.filters &&
    /^\d{4}-\d{2}-\d{2}$/.test(entry.filters.as_of_date) &&
    ["business_unit_id", "location_id", "department_id", "budget_id", "report_scope"].every(key => typeof entry.filters[key as keyof ReportFilters] === "string") &&
    typeof entry.filters.kap === "boolean" && typeof entry.filters.include_zero === "boolean";
};
export function loadReportPreferences(owner: string, kind: string, search: string, defaults: ReportFilters, storage = browserDraftStorage()): ReportPreferences {
  const saved = storage ? readDraft(storage, draftKey(owner, `report:${kind}`), valid) : null;
  const query = new URLSearchParams(search);
  const explicit = Object.keys(defaults).some(key => query.has(key));
  const filters = { ...(explicit ? defaults : saved?.filters ?? defaults) };
  for (const key of Object.keys(defaults) as (keyof ReportFilters)[]) {
    if (query.has(key)) {
      const value = query.get(key) ?? "";
      if (key === "kap" || key === "include_zero") filters[key] = value === "true";
      else filters[key] = value;
    }
  }
  return { filters, period: query.get("period") === "YTD" ? "YTD" : query.get("period") === "MTD" ? "MTD" : saved?.period ?? "MTD", view: saved?.view ?? "DETAIL" };
}
export function saveReportPreferences(owner: string, kind: string, value: ReportPreferences, storage = browserDraftStorage()) {
  if (storage) writeDraft(storage, draftKey(owner, `report:${kind}`), value);
}
