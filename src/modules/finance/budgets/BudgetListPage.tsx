import useAuthStore from "@/store/auth";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ListFilter, Plus } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Button from "@/components/ui/Button";
import { listBudgets, budgetAction } from "./api";
const money = (value: string) => Number(value).toLocaleString("id-ID");
export default function BudgetListPage() {
  const canManage = useAuthStore(state => state.hasPermission("finance.manage"));
  const [year, setYear] = useState(new Date().getFullYear());
  const [showFilters, setShowFilters] = useState(false);
  const [page, setPage] = useState(1);
  const client = useQueryClient();
  const query = useQuery({ queryKey: ["budgets", year, page], queryFn: () => listBudgets({ fiscal_year: year, page, page_size: 100 }) });
  const action = useMutation({ mutationFn: ({ id, name }: { id: number; name: string }) => budgetAction(id, name), onSuccess: () => { client.invalidateQueries({ queryKey: ["budgets"] }); client.invalidateQueries({ queryKey: ["financial-report-comparison"] }); }, onError: (error: { response?: { data?: { detail?: string } } }) => toast.error(error.response?.data?.detail || "Budget action failed") });
  return <div className="space-y-2"><PageHeader title="Budgets" description={String(year)} actions={<><Button size="sm" variant="outline" aria-label="Budget filters" title="Filters" onClick={() => setShowFilters(!showFilters)}><ListFilter size={15} /></Button>{canManage && <Link className="inline-flex h-8 items-center gap-1 rounded bg-blue-600 px-2 text-xs text-white" to="/budgets/new"><Plus size={15} />New</Link>}</>} />
    {showFilters && <label className="flex items-center gap-2 text-xs">Fiscal year<input className="h-8 rounded border px-2" type="number" min={2000} max={2100} value={year} onChange={event => { setYear(Number(event.target.value)); setPage(1); }} /></label>}
    {query.isError ? <p role="alert">Budgets could not be loaded.</p> : <div className="overflow-auto rounded border"><table className="w-full whitespace-nowrap text-xs"><thead className="bg-slate-100"><tr>{["Number", "Name", "Year", "Status", "Budget", "Actions"].map(name => <th key={name} className="px-2 py-1.5 text-left">{name}</th>)}</tr></thead><tbody>{query.data?.items?.map((budget: { id: number; budget_number: string; name: string; fiscal_year: number; status: string; total_budget: string; allowed_actions: Record<string, boolean> }) => <tr className="border-t" key={budget.id}><td className="p-2"><Link className="text-blue-700 hover:underline" to={`/budgets/${budget.id}`}>{budget.budget_number}</Link></td><td className="p-2">{budget.name}</td><td className="p-2">{budget.fiscal_year}</td><td className="p-2">{budget.status}</td><td className="p-2 text-right tabular-nums">{money(budget.total_budget)}</td><td className="flex gap-1 p-1">{canManage && budget.allowed_actions.can_edit && <Link className="rounded border px-2 py-1" to={`/budgets/${budget.id}/edit`}>Edit</Link>}{["submit", "approve", "lock"].filter(name => canManage && budget.allowed_actions[`can_${name}`]).map(name => <Button key={name} size="xs" variant="outline" disabled={action.isPending} onClick={() => action.mutate({ id: budget.id, name })}>{name.charAt(0).toUpperCase() + name.slice(1)}</Button>)}</td></tr>)}</tbody></table>{query.isLoading && <p className="p-3">Loading budgets…</p>}{!query.isLoading && !query.data?.items?.length && <p className="p-3 text-xs">No budgets for this year.</p>}</div>}
    <div className="flex items-center gap-2 text-xs"><Button size="xs" variant="outline" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</Button><span>{page} / {query.data?.total_pages || 1}</span><Button size="xs" variant="outline" disabled={page >= (query.data?.total_pages || 1)} onClick={() => setPage(page + 1)}>Next</Button></div>
  </div>;
}
