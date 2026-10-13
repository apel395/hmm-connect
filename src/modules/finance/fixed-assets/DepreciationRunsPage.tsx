import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Plus, Printer } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import ConfirmDialog from "@/components/common/ConfirmDialog";
import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Badge from "@/components/ui/Badge";
import { Table, THead, TBody, TR, TH, TD } from "@/components/ui/Table";
import { filterBusinessUnits, listLocations } from "@/modules/admin/organization/api";
import { createRun, listRuns, runAction } from "./api";
const now = new Date(), money = (value: number | string) => Number(value || 0).toLocaleString("id-ID");
const input = "mt-1 block h-9 rounded border px-2";

export default function DepreciationRunsPage() {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ period_year: now.getFullYear(), period_month: now.getMonth() + 1, business_unit_id: "", location_id: "", notes: "" });
  const [confirmation, setConfirmation] = useState<{ id: number; action: string; number: string } | null>(null);
  const runs = useQuery({ queryKey: ["depreciation-runs"], queryFn: listRuns });
  const units = useQuery({ queryKey: ["depreciation-run-units"], queryFn: () => filterBusinessUnits({ is_active: true }) });
  const locations = useQuery({ queryKey: ["depreciation-run-locations", form.business_unit_id], queryFn: () => listLocations({ business_unit_id: Number(form.business_unit_id), is_active: true }), enabled: Boolean(form.business_unit_id) });
  const refresh = () => { qc.invalidateQueries({ queryKey: ["depreciation-runs"] }); qc.invalidateQueries({ queryKey: ["fixed-asset"] }); qc.invalidateQueries({ queryKey: ["fixed-assets"] }); };
  const fail = (error: any) => toast.error(error?.response?.data?.detail || "Depreciation action failed");
  const create = useMutation({ mutationFn: () => createRun({ ...form, business_unit_id: Number(form.business_unit_id), location_id: Number(form.location_id) || null }), onSuccess: () => { refresh(); setShowForm(false); }, onError: fail });
  const act = useMutation({ mutationFn: ({ id, action }: { id: number; action: string }) => runAction(id, action), onSuccess: () => { refresh(); setConfirmation(null); }, onError: fail });
  return <div className="space-y-3">
    <PageHeader title="Depreciation Runs" actions={<><WorkspaceBackButton /><Button variant="outline" onClick={() => setShowForm(!showForm)}><Plus size={15} /></Button><Button variant="outline" onClick={() => window.print()}><Printer size={15} /></Button></>} />
    {showForm && <Card className="flex flex-wrap items-end gap-3 p-3 text-sm">
      <label>Year<input className={input} type="number" value={form.period_year} onChange={e => setForm({ ...form, period_year: Number(e.target.value) })} /></label>
      <label>Month<input className={`${input} w-20`} type="number" min={1} max={12} value={form.period_month} onChange={e => setForm({ ...form, period_month: Number(e.target.value) })} /></label>
      <label>Business Unit<select className={input} value={form.business_unit_id} onChange={e => setForm({ ...form, business_unit_id: e.target.value, location_id: "" })}><option value="">Select unit</option>{units.data?.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}</select></label>
      <label>Work Location<select className={input} disabled={!form.business_unit_id} value={form.location_id} onChange={e => setForm({ ...form, location_id: e.target.value })}><option value="">Unit level</option>{locations.data?.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label>
      <Button loading={create.isPending} disabled={!form.business_unit_id} onClick={() => create.mutate()}>New Run</Button>
    </Card>}
    {runs.isError && <p role="alert" className="text-sm text-red-700">Depreciation runs could not be loaded.</p>}
    <Table variant="grid" stickyHeader><THead><TR><TH>Run Number</TH><TH>Period</TH><TH>Assets</TH><TH className="text-right">Depreciation</TH><TH>Status</TH><TH>Journal</TH><TH>Actions</TH></TR></THead><TBody>{runs.data?.map((run: any) => <TR key={run.id}>
      <TD>{run.run_number}</TD><TD>{run.period_year}-{String(run.period_month).padStart(2, "0")}</TD><TD>{run.asset_count}</TD><TD className="text-right tabular-nums">{money(run.total_depreciation)}</TD><TD><Badge>{run.status}</Badge></TD><TD>{run.journal_entry_id ? <Link className="text-emerald-700 underline" to={`/journals/${run.journal_entry_id}`}>{run.journal_entry_id}</Link> : "—"}</TD>
      <TD className="space-x-1">{["DRAFT", "CALCULATED"].includes(run.status) && <Button size="xs" disabled={act.isPending} onClick={() => act.mutate({ id: run.id, action: "calculate" })}>Calculate</Button>}{run.status === "CALCULATED" && <Button size="xs" disabled={act.isPending || !run.asset_count} onClick={() => setConfirmation({ id: run.id, action: "post", number: run.run_number })}>Post</Button>}{run.status === "POSTED" && <Button size="xs" variant="outline" disabled={act.isPending} onClick={() => setConfirmation({ id: run.id, action: "unpost", number: run.run_number })}>Unpost</Button>}</TD>
    </TR>)}</TBody></Table>
    <ConfirmDialog open={Boolean(confirmation)} title={`${confirmation?.action === "unpost" ? "Unpost" : "Post"} ${confirmation?.number || ""}`} message={confirmation?.action === "unpost" ? "Restore asset book values and remove this run's GL posting? The journal will remain void in history." : "Post the calculated depreciation for this run?"} loading={act.isPending} onClose={() => setConfirmation(null)} onConfirm={() => confirmation && act.mutate(confirmation)} />
  </div>;
}
