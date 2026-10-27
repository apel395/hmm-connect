import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Button from "@/components/ui/Button";
import { operationsApi, type OutletSetupRow, type OrderMode } from "./operationsApi";

const field = "h-9 rounded border border-slate-300 bg-white px-2 text-sm";
const outletCode = (name: string) => name.normalize("NFD").replace(/[\u0300-\u036f]/g, "").replace(/[^a-z]/gi, "").slice(0, 3).toUpperCase();

type Props = { userId?: number; locationId: number; canManage: boolean; onSaved: (id?: number) => void };
export default function OutletSetup({ userId, locationId, canManage, onSaved }: Props) {
  const client = useQueryClient();
  const [expanded, setExpanded] = useState(false);
  const [editing, setEditing] = useState<OutletSetupRow | null>(null);
  const [name, setName] = useState("");
  const [code, setCode] = useState("");
  const [codeEdited, setCodeEdited] = useState(false);
  const [parent, setParent] = useState<number>();
  const [mode, setMode] = useState<OrderMode>("TABLE");
  const [active, setActive] = useState(true);
  const query = useQuery({ queryKey: ["pos-outlet-setup", userId, locationId], queryFn: async () => (await operationsApi.outlets(locationId)).data, enabled: canManage && expanded });
  const parentId = parent ?? query.data?.parents[0]?.id;
  const reset = () => { setEditing(null); setName(""); setCode(""); setCodeEdited(false); setMode("TABLE"); setActive(true); };
  const save = useMutation({ mutationFn: async () => (await operationsApi.saveOutlet({ location_id: locationId, parent_department_id: parentId!, name: name.trim(), code, order_mode: mode, is_active: active }, editing?.id)).data,
    onSuccess: async (row) => {
      await Promise.all([client.invalidateQueries({ queryKey: ["pos-options"] }), client.invalidateQueries({ queryKey: ["pos-outlet-setup"] }), client.invalidateQueries({ queryKey: ["pos-operations"] })]);
      onSaved(row.is_active ? row.id : undefined); reset();
    } });
  const edit = (row: OutletSetupRow) => { setEditing(row); setName(row.name); setCode(row.code); setCodeEdited(true); setParent(row.parent_department_id); setMode(row.order_mode ?? "TABLE"); setActive(row.is_active); save.reset(); };
  const detail = (save.error as any)?.response?.data?.detail;
  if (!canManage) return null;
  return <section className="print:hidden">
    <Button size="sm" variant="outline" onClick={() => setExpanded(value => !value)} aria-expanded={expanded}>Manage F&amp;B outlets</Button>
    {expanded && <div className="mt-2 space-y-2 rounded border bg-white p-3">
      {query.isLoading ? <p className="text-sm">Loading outlet setup…</p> : query.isError ? <p role="alert" className="text-sm text-red-700">Outlet setup could not load. <button className="underline" onClick={() => void query.refetch()}>Retry</button></p> : query.data?.parents.length === 0 ? <p className="text-sm">Assign the existing Food &amp; Beverage department to this Hotel location in Master Data first.</p> : query.data && <>
        <div className="flex flex-wrap items-end gap-2">
          {query.data.parents.length > 1 && <label className="text-xs">Department<select aria-label="Outlet parent department" className={`block ${field}`} value={parentId} disabled={Boolean(editing) || save.isPending} onChange={e => setParent(Number(e.target.value))}>{query.data.parents.map(row => <option key={row.id} value={row.id}>{row.name}</option>)}</select></label>}
          <label className="text-xs">Outlet name<input aria-label="Outlet name" className={`block ${field}`} placeholder="Restaurant, Coffee Shop…" maxLength={100} value={name} disabled={save.isPending} onChange={e => { setName(e.target.value); if (!codeEdited) setCode(outletCode(e.target.value)); }} /></label>
          <label className="text-xs">Code<input aria-label="Outlet code" className={`block ${field} w-20 uppercase`} maxLength={3} value={code} disabled={save.isPending} onChange={e => { setCodeEdited(true); setCode(e.target.value.replace(/[^a-z]/gi, "").toUpperCase()); }} /></label>
          <label className="text-xs">Orders<select aria-label="New outlet order mode" className={`block ${field}`} value={mode} disabled={save.isPending} onChange={e => setMode(e.target.value as OrderMode)}><option value="TABLE">Table · restaurant</option><option value="COUNTER">Counter · coffee shop</option><option value="EVENT">Event · banquet</option></select></label>
          {editing && <label className="flex h-9 items-center gap-1 text-sm"><input type="checkbox" checked={active} disabled={save.isPending} onChange={e => setActive(e.target.checked)} />Active</label>}
          <Button size="sm" disabled={!name.trim() || !/^[A-Z]{3}$/.test(code) || !parentId || save.isPending} onClick={() => save.mutate()}>{save.isPending ? "Saving…" : editing ? "Save outlet" : "Create outlet"}</Button>
          {editing && <Button size="sm" variant="ghost" disabled={save.isPending} onClick={() => { reset(); save.reset(); }}>Cancel</Button>}
        </div>
        {save.isError && <p role="alert" className="text-sm text-red-700">{typeof detail === "string" ? detail : "Outlet could not save. Check the name and three-letter code, then retry."}</p>}
        <div className="flex flex-wrap gap-2">{query.data.outlets.map(row => <button key={row.id} type="button" disabled={save.isPending} onClick={() => edit(row)} className="rounded border px-2 py-1 text-sm hover:bg-slate-50"><strong>{row.code}</strong> · {row.name}{!row.is_active ? " · Inactive" : ""} · Edit</button>)}</div>
      </>}
    </div>}
  </section>;
}
