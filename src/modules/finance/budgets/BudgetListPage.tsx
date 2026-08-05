import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import { listBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { createBudget, importBudget, listBudgets } from "./api";

const year = new Date().getFullYear();
const money = (value: unknown) => Number(value || 0).toLocaleString("id-ID");
const input = "h-9 rounded border px-2 text-sm";
const emptyLine = { month: 1, account_id: "", business_unit_id: "", location_id: "", department_id: "", budget_amount: "0", notes: "" };

export default function BudgetListPage() {
  const navigate = useNavigate();
  const [filters, setFilters] = useState<any>({ fiscal_year: year, status: "", business_unit_id: "", search: "" });
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<any>(null);
  const [form, setForm] = useState<any>({ name: "", fiscal_year: year, date_from: `${year}-01-01`, date_to: `${year}-12-31`, currency: "IDR", description: "", lines: [{ ...emptyLine }] });
  const budgets = useQuery({ queryKey: ["budgets", filters], queryFn: () => listBudgets(filters) });
  const businessUnits = useQuery({ queryKey: ["business-units"], queryFn: listBusinessUnits });
  const accounts = useQuery({ queryKey: ["budget-accounts"], queryFn: () => getAccountLookup({ is_active: true, is_posting: true }) });
  const create = useMutation({ mutationFn: () => createBudget({ ...form, lines: form.lines.map((line: any) => ({ ...line, month: Number(line.month), account_id: Number(line.account_id), business_unit_id: Number(line.business_unit_id), location_id: line.location_id ? Number(line.location_id) : null, department_id: line.department_id ? Number(line.department_id) : null })) }), onSuccess: (budget: any) => navigate(`/budgets/${budget.id}`) });
  const updateLine = (index: number, key: string, value: unknown) => setForm({ ...form, lines: form.lines.map((line: any, row: number) => row === index ? { ...line, [key]: value, ...(key === "business_unit_id" ? { location_id: "", department_id: "" } : {}) } : line) });
  const total = form.lines.reduce((sum: number, line: any) => sum + Number(line.budget_amount || 0), 0);

  return <div className="space-y-4">
    <PageHeader title="Budgets" description="Approved planning by organization dimension, period, and account." actions={<>
      <a className="inline-flex h-9 items-center rounded border px-3 text-sm" href="/api/v1/budgets/template">Download Template</a>
      <label className="inline-flex h-9 cursor-pointer items-center rounded border px-3 text-sm">Import Budget<input hidden type="file" accept=".csv,.xlsx" onChange={async event => { const selected = event.target.files?.[0]; if (selected) { setFile(selected); setPreview(await importBudget(selected, true)); } }} /></label>
      <Button onClick={() => setOpen(true)}>New Budget</Button>
    </>} />
    <Card className="p-3"><div className="flex flex-wrap gap-2"><input className={input} type="number" value={filters.fiscal_year} onChange={event => setFilters({ ...filters, fiscal_year: event.target.value })} /><select className={input} value={filters.status} onChange={event => setFilters({ ...filters, status: event.target.value })}><option value="">All statuses</option>{["DRAFT", "SUBMITTED", "APPROVED", "LOCKED", "REJECTED", "CANCELLED"].map(status => <option key={status}>{status}</option>)}</select><select className={input} value={filters.business_unit_id} onChange={event => setFilters({ ...filters, business_unit_id: event.target.value })}><option value="">All business units</option>{businessUnits.data?.map((unit: any) => <option key={unit.id} value={unit.id}>{unit.name}</option>)}</select><input className={input} placeholder="Search" value={filters.search} onChange={event => setFilters({ ...filters, search: event.target.value })} /></div></Card>
    {preview && <Card className="flex items-center justify-between p-3"><span>Detected {preview.rows_detected}; accepted {preview.rows_accepted}; errors {preview.errors.length}</span><Button disabled={!file || preview.errors.length} onClick={async () => file && navigate(`/budgets/${(await importBudget(file, false)).budget_id}`)}>Confirm Import</Button></Card>}
    <Table variant="grid"><THead><TR><TH>Budget Number</TH><TH>Name</TH><TH>Fiscal Year</TH><TH>Period</TH><TH className="text-right">Total Budget</TH><TH>Status</TH><TH>Created By</TH><TH>Actions</TH></TR></THead><TBody>{budgets.data?.items?.map((budget: any) => <TR key={budget.id}><TD>{budget.budget_number}</TD><TD>{budget.name}</TD><TD>{budget.fiscal_year}</TD><TD>{budget.date_from} – {budget.date_to}</TD><TD className="text-right tabular-nums">{money(budget.total_budget)}</TD><TD><Badge>{budget.status}</Badge></TD><TD>{budget.created_by}</TD><TD><Button size="xs" variant="outline" onClick={() => navigate(`/budgets/${budget.id}`)}>View</Button></TD></TR>)}</TBody></Table>
    {open && <div className="fixed inset-0 z-50 overflow-auto bg-black/40 p-8"><Card className="mx-auto max-w-6xl p-4"><h2 className="font-semibold">New Budget</h2><div className="my-3 grid gap-2 md:grid-cols-6"><input className={input} placeholder="Name" value={form.name} onChange={event => setForm({ ...form, name: event.target.value })} /><input className={input} type="number" value={form.fiscal_year} onChange={event => setForm({ ...form, fiscal_year: Number(event.target.value) })} /><input className={input} type="date" value={form.date_from} onChange={event => setForm({ ...form, date_from: event.target.value })} /><input className={input} type="date" value={form.date_to} onChange={event => setForm({ ...form, date_to: event.target.value })} /><input className={input} value={form.currency} onChange={event => setForm({ ...form, currency: event.target.value })} /><input className={input} placeholder="Description" value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} /></div>
      <Table variant="grid"><THead><TR><TH>Month</TH><TH>Business Unit</TH><TH>Location</TH><TH>Department</TH><TH>COA Account</TH><TH>Budget Amount</TH><TH>Notes</TH><TH /></TR></THead><TBody>{form.lines.map((line: any, index: number) => <BudgetLineRow key={index} line={line} businessUnits={businessUnits.data || []} accounts={accounts.data || []} onChange={(key: string, value: unknown) => updateLine(index, key, value)} onRemove={() => setForm({ ...form, lines: form.lines.filter((_: any, row: number) => row !== index) })} />)}</TBody></Table>
      <div className="mt-3 flex justify-between"><div><Button variant="outline" onClick={() => setForm({ ...form, lines: [...form.lines, { ...(form.lines.at(-1) || emptyLine) }] })}>Add / Duplicate Row</Button><span className="ml-4 text-sm">Total: <b className="tabular-nums">{money(total)}</b></span></div><div className="flex gap-2"><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button disabled={create.isPending} onClick={() => create.mutate()}>Save Draft</Button></div></div>
    </Card></div>}
  </div>;
}

function BudgetLineRow({ line, businessUnits, accounts, onChange, onRemove }: any) {
  const unitId = Number(line.business_unit_id) || undefined;
  const locations = useQuery({ queryKey: ["budget-locations", unitId], queryFn: () => listLocations(unitId), enabled: !!unitId });
  const departments = useQuery({ queryKey: ["budget-departments", unitId], queryFn: () => listDepartments(unitId), enabled: !!unitId });
  return <TR><TD><input className={`${input} w-20`} type="number" min={1} max={12} value={line.month} onChange={event => onChange("month", event.target.value)} /></TD><TD><select className={input} value={line.business_unit_id} onChange={event => onChange("business_unit_id", event.target.value)}><option value="">Select</option>{businessUnits.map((unit: any) => <option key={unit.id} value={unit.id}>{unit.code}</option>)}</select></TD><TD><select className={input} value={line.location_id} onChange={event => onChange("location_id", event.target.value)} disabled={!unitId}><option value="">All</option>{locations.data?.map((location: any) => <option key={location.id} value={location.id}>{location.name}</option>)}</select></TD><TD><select className={input} value={line.department_id} onChange={event => onChange("department_id", event.target.value)} disabled={!unitId}><option value="">All</option>{departments.data?.map((department: any) => <option key={department.id} value={department.id}>{department.name}</option>)}</select></TD><TD><select className={input} value={line.account_id} onChange={event => onChange("account_id", event.target.value)}><option value="">Select account</option>{accounts.map((account: any) => <option key={account.id} value={account.id}>{account.account_number} — {account.account_name}</option>)}</select></TD><TD><input className={`${input} w-36 text-right tabular-nums`} type="number" min={0} step="0.01" value={line.budget_amount} onChange={event => onChange("budget_amount", event.target.value)} /></TD><TD><input className={input} value={line.notes} onChange={event => onChange("notes", event.target.value)} /></TD><TD><Button size="xs" variant="danger" onClick={onRemove}>Remove</Button></TD></TR>;
}
