import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import Pagination from "@/components/datatable/Pagination";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Input from "@/components/ui/Input";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import useAuthorization from "@/hooks/useAuthorization";
import {
  BusinessUnit, OrganizationPayload, OrganizationRecord,
  createBusinessUnit, createDepartment, createLocation, filterBusinessUnits,
  listDepartments, listLocations,
  updateBusinessUnit, updateDepartment, updateLocation,
} from "./api";

export type OrganizationSection = "business-units" | "departments" | "locations";
interface Props { fixedSection?: OrganizationSection }
const labels = { "business-units": "Business Units", departments: "Departments", locations: "Locations" };
const blank = (): OrganizationPayload => ({ code: "", name: "", is_active: true, location_type: "OFFICE", department_ids: [], parent_department_id: null });
const errorMessage = (error: any) => error?.response?.data?.detail || "The master-data record could not be saved.";
const PAGE_SIZE = 25;

export default function OrganizationManagement({ fixedSection }: Props) {
  const queryClient = useQueryClient();
  const { canPerform } = useAuthorization();
  const canManage = canPerform("edit", ["ADMIN", "ADMINISTRATOR", "MASTER_DATA"]);
  const [section, setSection] = useState<OrganizationSection>(fixedSection ?? "business-units");
  const [businessUnitId, setBusinessUnitId] = useState<number | undefined>();
  const [activeOnly, setActiveOnly] = useState(false);
  const [locationType, setLocationType] = useState("");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [formVisible, setFormVisible] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<OrganizationPayload>(blank());

  useEffect(() => { if (fixedSection) setSection(fixedSection); }, [fixedSection]);
  useEffect(() => { setEditingId(null); setForm(blank()); setFormVisible(false); setPage(1); }, [section]);
  useEffect(() => { setPage(1); }, [search, activeOnly, businessUnitId, locationType]);

  const units = useQuery({ queryKey: ["business-units", activeOnly, search], queryFn: () => filterBusinessUnits({ is_active: activeOnly || undefined, search: search || undefined }) });
  const filters = { business_unit_id: businessUnitId, location_type: locationType || undefined, is_active: activeOnly || undefined, search: search || undefined };
  const departments = useQuery({ queryKey: ["departments", filters], queryFn: () => listDepartments(filters), enabled: section === "departments" });
  const availableDepartments = useQuery({ queryKey: ["location-department-options", form.business_unit_id], queryFn: () => listDepartments({ business_unit_id: form.business_unit_id ?? undefined }), enabled: section === "locations" && Boolean(form.business_unit_id) });
  const outletParents = useQuery({ queryKey: ["outlet-parent-options", form.business_unit_id], queryFn: () => listDepartments({ business_unit_id: form.business_unit_id ?? undefined, is_active: true }), enabled: section === "departments" && Boolean(form.business_unit_id) });
  const locations = useQuery({ queryKey: ["locations", filters], queryFn: () => listLocations(filters), enabled: section === "locations" });
  const rows: OrganizationRecord[] = section === "business-units" ? units.data ?? [] : section === "departments" ? departments.data ?? [] : locations.data ?? [];
  const pages = Math.max(Math.ceil(rows.length / PAGE_SIZE), 1);
  const visibleRows = rows.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);

  const save = useMutation({
    mutationFn: async () => {
      if (section === "business-units") return editingId ? updateBusinessUnit(editingId, form) : createBusinessUnit(form);
      if (section === "departments") return editingId ? updateDepartment(editingId, form) : createDepartment(form);
      return editingId ? updateLocation(editingId, form) : createLocation(form);
    },
    onSuccess: () => {
      toast.success(`${labels[section].slice(0, -1)} ${editingId ? "updated" : "created"}.`);
      queryClient.invalidateQueries({ queryKey: ["outlet-parent-options"] });
      queryClient.invalidateQueries({ queryKey: ["location-department-options"] });
      queryClient.invalidateQueries({ queryKey: ["locations"] });
      setEditingId(null); setForm(blank()); setFormVisible(false); queryClient.invalidateQueries({ queryKey: [section] });
      queryClient.invalidateQueries({ predicate: query => query.queryKey.some(key => typeof key === "string" && key.includes("department")) });
      if (section === "business-units") queryClient.invalidateQueries({ queryKey: ["business-units"] });
    },
    onError: (error) => toast.error(errorMessage(error)),
  });
  const toggleActive = useMutation({
    mutationFn: async (row: OrganizationRecord) => {
      if (row.is_active && !window.confirm(`Deactivate ${row.code}? Existing references will be preserved.`)) return null;
      const payload = { is_active: !row.is_active };
      if (section === "business-units") return updateBusinessUnit(row.id, payload);
      if (section === "departments") return updateDepartment(row.id, payload);
      return updateLocation(row.id, payload);
    },
    onSuccess: (result) => { if (result) { toast.success(`Record ${result.is_active ? "reactivated" : "deactivated"}.`); queryClient.invalidateQueries({ queryKey: [section] }); } },
    onError: (error) => toast.error(errorMessage(error)),
  });

  const edit = (row: OrganizationRecord) => { setEditingId(row.id); setForm({ ...row, code: row.code, name: row.name }); };
  const update = (key: string, value: unknown) => setForm((current) => ({ ...current, [key]: value }));
  const needsUnit = section === "locations";
  const valid = form.code.trim() && form.name.trim() && (!needsUnit || form.business_unit_id);

  return <div className="workspace-body">
    {!fixedSection && <Card className="flex flex-wrap gap-2 p-3">{(Object.keys(labels) as OrganizationSection[]).map((item) => <Button key={item} variant={section === item ? "primary" : "outline"} onClick={() => setSection(item)}>{labels[item]}</Button>)}</Card>}
    <Card className="workspace-data p-2">
      <div className="flex flex-wrap items-end gap-3">
        <label className="min-w-56 flex-1 text-xs font-medium text-slate-600">Search<Input className="mt-1" placeholder="Search code or name" value={search} onChange={(event) => setSearch(event.target.value)} /></label>
        {section !== "business-units" && <label className="min-w-56 text-xs font-medium text-slate-600">Business Unit<select className="mt-1 h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-[13px]" value={businessUnitId ?? ""} onChange={(event) => setBusinessUnitId(event.target.value ? Number(event.target.value) : undefined)}><option value="">All business units</option>{(units.data ?? []).map((unit: BusinessUnit) => <option key={unit.id} value={unit.id}>{unit.code} — {unit.name}</option>)}</select></label>}
        {section === "locations" && <label className="min-w-44 text-xs font-medium text-slate-600">Location Type<select className="mt-1 h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-[13px]" value={locationType} onChange={(event) => setLocationType(event.target.value)}><option value="">All types</option>{["OFFICE", "WAREHOUSE", "SITE", "STORE", "OTHER"].map((type) => <option key={type}>{type}</option>)}</select></label>}
        <label className="flex h-9 items-center gap-2 text-sm"><input type="checkbox" checked={activeOnly} onChange={(event) => setActiveOnly(event.target.checked)} />Active only</label>
      </div>
      {canManage && <div className="flex justify-end"><Button size="sm" variant="outline" aria-expanded={formVisible} onClick={() => setFormVisible(!formVisible)}>{formVisible ? "Close form" : "New record"}</Button></div>}
      {canManage && formVisible && <form className="grid gap-3 rounded-md border border-slate-200 bg-slate-50 p-3 md:grid-cols-2 xl:grid-cols-4" onSubmit={(event) => { event.preventDefault(); save.mutate(); }}>
        <label className="text-xs font-medium text-slate-600">Code<Input required className="mt-1" value={form.code} onChange={(event) => update("code", event.target.value)} /></label>
        <label className="text-xs font-medium text-slate-600">Name<Input required className="mt-1" value={form.name} onChange={(event) => update("name", event.target.value)} /></label>
        {section === "business-units" && <label className="text-xs font-medium text-slate-600">Description<Input className="mt-1" value={form.description ?? ""} onChange={(event) => update("description", event.target.value)} /></label>}
        {section !== "business-units" && <label className="text-xs font-medium text-slate-600">Business Unit<select required={needsUnit} className="mt-1 h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-[13px]" value={form.business_unit_id ?? ""} onChange={(event) => { update("business_unit_id", event.target.value ? Number(event.target.value) : null); if (section === "locations") update("department_ids", []); if (section === "departments") update("parent_department_id", null); }}><option value="">{section === "departments" ? "Shared / company-wide" : "Select business unit"}</option>{(units.data ?? []).filter((unit) => unit.is_active || unit.id === form.business_unit_id).map((unit) => <option key={unit.id} value={unit.id}>{unit.code} — {unit.name}</option>)}</select></label>}
        {section === "departments" && <label className="text-xs font-medium text-slate-600">Parent department / Hotel outlet<select className="mt-1 h-9 w-full rounded-md border border-slate-300 bg-white px-3 text-[13px]" value={form.parent_department_id ?? ""} onChange={event => update("parent_department_id", event.target.value ? Number(event.target.value) : null)} disabled={!form.business_unit_id || outletParents.isLoading || outletParents.isError}><option value="">Independent department</option>{(outletParents.data ?? []).filter(department => department.id !== editingId && !department.parent_department_id && /hotel/i.test(department.business_unit_name ?? "")).map(department => <option key={department.id} value={department.id}>{department.name}</option>)}</select>{outletParents.isError && <span role="alert">Parent departments could not be loaded.</span>}</label>}
        {section === "locations" && <><label className="text-xs font-medium text-slate-600">Location Type<Input className="mt-1" value={form.location_type ?? "OFFICE"} onChange={(event) => update("location_type", event.target.value)} /></label><label className="text-xs font-medium text-slate-600">Address<Input className="mt-1" value={form.address ?? ""} onChange={(event) => update("address", event.target.value)} /></label><label className="text-xs font-medium text-slate-600">City<Input className="mt-1" value={form.city ?? ""} onChange={(event) => update("city", event.target.value)} /></label><label className="text-xs font-medium text-slate-600">Province<Input className="mt-1" value={form.province ?? ""} onChange={(event) => update("province", event.target.value)} /></label><label className="text-xs font-medium text-slate-600">Postal Code<Input className="mt-1" value={form.postal_code ?? ""} onChange={(event) => update("postal_code", event.target.value)} /></label></>}
        {section === "locations" && <fieldset className="md:col-span-2 xl:col-span-4"><legend className="text-xs font-medium text-slate-600">Departments</legend><div className="mt-1 flex flex-wrap gap-x-4 gap-y-2">{(availableDepartments.data ?? []).filter(department => department.is_active || form.department_ids?.includes(department.id)).map(department => <label key={department.id} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.department_ids?.includes(department.id) ?? false} onChange={event => update("department_ids", event.target.checked ? [...(form.department_ids ?? []), department.id] : (form.department_ids ?? []).filter(id => id !== department.id))} />{department.code} — {department.name}</label>)}{!form.business_unit_id && <span className="text-xs text-slate-500">Select a business unit first.</span>}{availableDepartments.isLoading && <span className="text-xs">Loading departments…</span>}{availableDepartments.isError && <span role="alert" className="text-xs text-red-600">Departments could not be loaded.</span>}{form.business_unit_id && availableDepartments.isSuccess && !availableDepartments.data.length && <span className="text-xs text-slate-500">Create a department in Departments first.</span>}</div></fieldset>}
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={form.is_active ?? true} onChange={(event) => update("is_active", event.target.checked)} />Active</label>
        <div className="flex items-end gap-2"><Button type="submit" loading={save.isPending} disabled={!valid || (section === "locations" && (availableDepartments.isLoading || availableDepartments.isError))}>{editingId ? "Update" : "Create"}</Button>{editingId && <Button type="button" variant="outline" onClick={() => { setEditingId(null); setForm(blank()); setFormVisible(false); }}>Cancel</Button>}</div>
      </form>}
      <div className="workspace-table-stack"><Table variant="standard"><THead><TR><TH>Code</TH><TH>Name</TH>{section !== "business-units" && <TH>Business Unit</TH>}{section === "departments" && <TH>Parent department</TH>}{section === "locations" && <><TH>Type</TH><TH>City</TH></>}<TH>Status</TH>{canManage && <TH>Actions</TH>}</TR></THead><TBody>{visibleRows.map((row) => <TR key={row.id}><TD className="font-medium">{row.code}</TD><TD>{row.name}</TD>{section !== "business-units" && <TD>{"business_unit_name" in row ? row.business_unit_name || "Shared / company-wide" : "—"}</TD>}{section === "departments" && <TD>{"parent_department_name" in row ? row.parent_department_name || "—" : "—"}</TD>}{section === "locations" && <><TD>{"location_type" in row ? row.location_type : "—"}</TD><TD>{"city" in row ? row.city || "—" : "—"}</TD></>}<TD>{row.is_active ? "Active" : "Inactive"}</TD>{canManage && <TD><div className="flex gap-2"><Button size="xs" variant="outline" onClick={() => { setFormVisible(true); edit(row); }}>Edit</Button><Button size="xs" variant={row.is_active ? "danger" : "success"} loading={toggleActive.isPending && toggleActive.variables?.id === row.id} onClick={() => toggleActive.mutate(row)}>{row.is_active ? "Deactivate" : "Reactivate"}</Button></div></TD>}</TR>)}</TBody></Table>{(units.isLoading || departments.isLoading || locations.isLoading) && <p className="py-8 text-center text-sm text-slate-500">Loading records…</p>}{(units.isError || departments.isError || locations.isError) && <p className="py-8 text-center text-sm text-red-600">Master data could not be loaded.</p>}{rows.length === 0 && !(units.isLoading || departments.isLoading || locations.isLoading) && <p className="py-8 text-center text-sm text-slate-500">No records found.</p>}</div>
      {rows.length > 0 && <Pagination page={page} pages={pages} total={rows.length} pageSize={PAGE_SIZE} noun={labels[section].toLowerCase()} onChange={setPage}/>} 
    </Card>
  </div>;
}
