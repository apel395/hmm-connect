import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";
import api from "@/api/client";
import Button from "@/components/ui/Button";
import PageHeader from "@/components/common/PageHeader";
import { listBusinessUnits, listLocations, listDepartments } from "@/modules/admin/organization/api";
import { createBudget, updateBudget, getBudget } from "./api";

type Line = { account_id: number; business_unit_id: number; location_id: number | null; department_id: number | null; month: number; budget_amount: string; notes?: string | null; location_name?: string; business_unit_name?: string };
type Budget = { name: string; fiscal_year: number; status?: string; lines: Line[] };
type Account = { id: number; code: string; name: string; type: string; is_posting: boolean };
const input = "h-8 rounded border px-2 text-xs";
export default function BudgetFormPage() {
  const id = Number(useParams().id) || 0;
  const query = useQuery({ queryKey: ["budget", id], queryFn: () => getBudget(id), enabled: !!id });
  if (id && query.isLoading) return <p>Loading budget…</p>;
  if (id && query.isError) return <p role="alert">Budget could not be loaded.</p>;
  if (id && query.data?.status !== "DRAFT") return <p>Only draft budgets can be edited.</p>;
  return <BudgetEditor key={id} id={id} initial={query.data} />;
}
function BudgetEditor({ id, initial }: { id: number; initial?: Budget }) {
  const [name, setName] = useState(initial?.name ?? "");
  const [year, setYear] = useState(initial?.fiscal_year ?? new Date().getFullYear());
  const [lines, setLines] = useState<Line[]>(initial?.lines ?? []);
  const [unit, setUnit] = useState(String(initial?.lines[0]?.business_unit_id ?? ""));
  const [location, setLocation] = useState(String(initial?.lines[0]?.location_id ?? ""));
  const [department, setDepartment] = useState(String(initial?.lines[0]?.department_id ?? ""));
  const [month, setMonth] = useState(1);
  const navigate = useNavigate();
  const client = useQueryClient();
  const accounts = useQuery({ queryKey: ["financial-report-setup"], queryFn: async () => (await api.get<{ accounts: Account[] }>("/financial-reports/setup")).data });
  const units = useQuery({ queryKey: ["report-units"], queryFn: listBusinessUnits });
  const locations = useQuery({ queryKey: ["budget-locations", unit], queryFn: () => listLocations({ is_active: true, business_unit_id: Number(unit) || undefined }) });
  const departments = useQuery({ queryKey: ["budget-departments", unit], queryFn: () => listDepartments({ is_active: true, business_unit_id: Number(unit) || undefined }) });
  const save = useMutation({ mutationFn: async () => {
    const payload = { name, fiscal_year: year, date_from: `${year}-01-01`, date_to: `${year}-12-31`, lines };
    return id ? updateBudget(id, payload) : createBudget(payload);
  }, onSuccess: (budget: { id: number }) => { client.invalidateQueries({ queryKey: ["budgets"] }); client.invalidateQueries({ queryKey: ["budget", id] }); toast.success("Budget saved"); navigate(`/budgets/${budget.id}`); }, onError: (error: { response?: { data?: { detail?: string } } }) => toast.error(error.response?.data?.detail || "Budget could not be saved") });
  const change = (index: number, values: Partial<Line>) => setLines(old => old.map((line, i) => i === index ? { ...line, ...values } : line));
  const available = accounts.data?.accounts.filter(account => account.is_posting && (!["REVENUE", "INCOME"].includes(account.type) || account.code === "400")) ?? [];
  return <form className="space-y-2" onSubmit={event => { event.preventDefault(); save.mutate(); }}><PageHeader title={id ? "Edit Budget" : "New Budget"} actions={<><Button type="button" size="sm" variant="outline" onClick={() => navigate("/budgets")}>Back</Button><Button type="submit" size="sm" disabled={save.isPending || !lines.length || lines.some(line => !line.account_id)}>Save draft</Button></>} />
    <div className="flex flex-wrap items-end gap-2"><label className="grid text-xs">Name<input required className={input} value={name} onChange={event => setName(event.target.value)} /></label><label className="grid text-xs">Year<input required min={2000} max={2100} type="number" className={`${input} w-24`} value={year} disabled={!!id} onChange={event => setYear(Number(event.target.value))} /></label>
      <label className="grid text-xs">Unit<select className={input} value={unit} onChange={event => { setUnit(event.target.value); setLocation(""); setDepartment(""); }}><option value="">Select unit</option>{units.data?.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <label className="grid text-xs">Location<select className={input} value={location} onChange={event => setLocation(event.target.value)}><option value="">Select location</option>{locations.data?.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <label className="grid text-xs">Department<select className={input} value={department} onChange={event => setDepartment(event.target.value)}><option value="">No department</option>{departments.data?.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>
      <label className="grid text-xs">Month<select className={input} value={month} onChange={event => setMonth(Number(event.target.value))}>{Array.from({ length: 12 }, (_, i) => <option key={i} value={i + 1}>{new Date(2000, i, 1).toLocaleString("en", { month: "short" })}</option>)}</select></label>
      <Button type="button" size="sm" variant="outline" disabled={!unit || !location} onClick={() => setLines([...lines, { account_id: 0, business_unit_id: Number(unit), location_id: Number(location), department_id: Number(department) || null, month, budget_amount: "0" }])}>Add line</Button>
    </div>
    <div className="overflow-auto rounded border"><table className="w-full whitespace-nowrap text-xs"><thead className="bg-slate-100"><tr>{["Month", "Account", "Unit / Location", "Budget", ""].map((label, i) => <th className="p-1.5 text-left" key={i}>{label}</th>)}</tr></thead><tbody>{lines.map((line, index) => <tr key={index} className="border-t"><td className="p-1"><select className={input} value={line.month} onChange={event => change(index, { month: Number(event.target.value) })}>{Array.from({ length: 12 }, (_, i) => <option key={i} value={i+1}>{i+1}</option>)}</select></td><td className="p-1"><select required className={`${input} min-w-64`} value={line.account_id || ""} onChange={event => change(index, { account_id: Number(event.target.value) })}><option value="">Select account</option>{available.map(a => <option key={a.id} value={a.id}>{a.code} {a.name}</option>)}</select></td><td className="p-1">{units.data?.find(row => row.id === line.business_unit_id)?.name} / {locations.data?.find(row => row.id === line.location_id)?.name || line.location_name || "—"}</td><td className="p-1"><input required aria-label={`Budget amount line ${index+1}`} type="number" min="0" step="0.01" className={`${input} text-right`} value={line.budget_amount} onChange={event => change(index, { budget_amount: event.target.value })} /></td><td className="p-1"><Button type="button" size="xs" variant="ghost" aria-label={`Remove budget line ${index+1}`} onClick={() => setLines(lines.filter((_, i) => i !== index))}><Trash2 size={14} /></Button></td></tr>)}</tbody></table></div>
  </form>;
}
