import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Filter } from "lucide-react";
import Button from "@/components/ui/Button";
import ReportUnitButtons from "@/components/reports/ReportUnitButtons";
import { listDepartments, listLocations } from "@/modules/admin/organization/api";
import { listCategories } from "./api";

export type AssetFilters = { business_unit_id?: number; location_id?: number; department_id?: number; category_id?: number; date_from?: string; date_to?: string; status?: string };
export default function AssetReportFilters({ value, onChange, depreciation = false }: { value: AssetFilters; onChange: (v: AssetFilters) => void; depreciation?: boolean }) {
  const [open, setOpen] = useState(false);
  const categories = useQuery({ queryKey: ["asset-categories"], queryFn: listCategories, enabled: open });
  const locations = useQuery({ queryKey: ["asset-report-locations", value.business_unit_id], queryFn: () => listLocations({ business_unit_id: value.business_unit_id, is_active: true }), enabled: open });
  const departments = useQuery({ queryKey: ["asset-report-departments", value.business_unit_id, value.location_id], queryFn: () => listDepartments({ business_unit_id: value.business_unit_id, location_id: value.location_id, is_active: true }), enabled: open });
  const selectClass = "h-8 rounded border bg-white px-2 text-xs";
  return <div className="print:hidden space-y-2">
    <div className="flex items-center justify-between gap-2"><ReportUnitButtons value={String(value.business_unit_id || "")} onChange={unit => onChange({ ...value, business_unit_id: Number(unit) || undefined, location_id: undefined, department_id: undefined })}/><Button variant="outline" title="Filters" aria-label="Filters" onClick={() => setOpen(!open)}><Filter size={15}/></Button></div>
    {open && <div className="flex flex-wrap gap-2">
      <select aria-label="Location" className={selectClass} value={value.location_id || ""} onChange={e => onChange({ ...value, location_id: Number(e.target.value) || undefined, department_id: undefined })}><option value="">All locations</option>{locations.data?.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}</select>
      <select aria-label="Department" className={selectClass} value={value.department_id || ""} onChange={e => onChange({ ...value, department_id: Number(e.target.value) || undefined })}><option value="">All departments</option>{departments.data?.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
      <select aria-label="Category" className={selectClass} value={value.category_id || ""} onChange={e => onChange({ ...value, category_id: Number(e.target.value) || undefined })}><option value="">All categories</option>{categories.data?.map((c: any) => <option key={c.id} value={c.id}>{c.name}</option>)}</select>
      {depreciation && <><input aria-label="From date" className={selectClass} type="date" value={value.date_from || ""} onChange={e => onChange({ ...value, date_from: e.target.value || undefined })}/><input aria-label="To date" className={selectClass} type="date" value={value.date_to || ""} onChange={e => onChange({ ...value, date_to: e.target.value || undefined })}/><select aria-label="Schedule status" className={selectClass} value={value.status || ""} onChange={e => onChange({ ...value, status: e.target.value || undefined })}><option value="">All schedules</option>{["POSTED", "PLANNED", "GENERATED", "SKIPPED"].map(s => <option key={s}>{s}</option>)}</select></>}
    </div>}
  </div>;
}
