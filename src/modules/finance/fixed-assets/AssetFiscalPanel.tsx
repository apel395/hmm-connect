import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import { getFiscalProfile, saveFiscalProfile } from "./api";

type Group = { code: string; name: string; months: number | null; straight_line_rate: string | null; declining_balance_rate: string | null };
type Profile = { group_code: string; method: string; fiscal_cost: string; start_date: string | null; useful_life_months: number | null; reference: string; opening_date: string | null; opening_book_value: string | null; version?: number };
const field = "block h-8 w-full rounded border px-2 text-sm";
export default function AssetFiscalPanel({ asset }: { asset: { id: number; acquisition_cost: string | null; acquisition_date: string; depreciation_start_date?: string; fiscal_group_code?: string | null } }) {
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState<Profile | null>(null);
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["asset-fiscal", asset.id], queryFn: () => getFiscalProfile(asset.id), enabled: open });
  const groups: Group[] = q.data?.groups ?? [];
  const save = useMutation({
    mutationFn: () => saveFiscalProfile(asset.id, { ...form, expected_version: form?.version ?? 0 }),
    onSuccess: () => { setForm(null); qc.invalidateQueries({ queryKey: ["asset-fiscal", asset.id] }); qc.invalidateQueries({ queryKey: ["asset-fiscal-report"] }); toast.success("Fiscal profile saved"); },
    onError: (e: any) => toast.error(typeof e?.response?.data?.detail === "string" ? e.response.data.detail : "Check fiscal profile fields and reload if another user changed it"),
  });
  const set = (values: Partial<Profile>) => form && setForm({ ...form, ...values });
  const group = groups.find(g => g.code === form?.group_code);
  return <section className="rounded border bg-white p-3 space-y-2">
    <button className="font-semibold" aria-expanded={open} onClick={() => setOpen(!open)}>Fiscal depreciation {open ? "−" : "+"}</button>
    {open && <>
      <p className="text-xs text-slate-600">Separate tax schedule · no GL posting. Book useful life and opening balances remain unchanged.</p>
      {q.isLoading && <p>Loading…</p>}{q.isError && <p role="alert">Could not load fiscal setup.</p>}
      {q.data && !form && <div className="flex items-center gap-3 text-sm"><span>{q.data.profile ? `${q.data.profile.group_code} · ${q.data.profile.method}` : "Not configured"}</span><Button size="xs" variant="outline" disabled={asset.acquisition_cost == null} onClick={() => setForm(q.data.profile ?? { group_code: asset.fiscal_group_code || "", method: asset.fiscal_group_code === "LAND" ? "NONE" : "STRAIGHT_LINE", fiscal_cost: asset.acquisition_cost ?? "", start_date: asset.fiscal_group_code === "LAND" ? null : asset.depreciation_start_date || asset.acquisition_date, useful_life_months: null, reference: "", opening_date: null, opening_book_value: null })}>Configure</Button></div>}
      {form && <form className="grid gap-3 md:grid-cols-3" onSubmit={e => { e.preventDefault(); save.mutate(); }}>
        <label className="text-sm">Fiscal group<select required className={field} value={form.group_code} onChange={e => set({ group_code: e.target.value, useful_life_months: null, ...(e.target.value === "LAND" ? { method: "NONE", start_date: null, opening_date: null, opening_book_value: null } : { method: "STRAIGHT_LINE", start_date: form.start_date || asset.acquisition_date }) })}><option value="">Choose fiscal group</option>{groups.map(g => <option key={g.code} value={g.code}>{g.name}{g.months ? ` · ${g.months / 12} years` : ""}</option>)}</select></label>
        <label className="text-sm">Method<select className={field} value={form.method} onChange={e => set({ method: e.target.value })}>{form.group_code === "LAND" ? <option value="NONE">Non-depreciable</option> : <><option value="STRAIGHT_LINE">Straight line ({form.useful_life_months ? (1200 / form.useful_life_months).toFixed(2) : group?.straight_line_rate}%)</option>{group?.declining_balance_rate && <option value="DECLINING_BALANCE">Declining balance ({group.declining_balance_rate}%)</option>}</>}</select></label>
        <label className="text-sm">Fiscal cost<input required type="number" min="0.01" step="0.01" className={field} value={form.fiscal_cost} onChange={e => set({ fiscal_cost: e.target.value })}/></label>
        {form.group_code !== "LAND" && <>
          <label className="text-sm">Fiscal start month<input required type="date" className={field} value={form.start_date ?? ""} onChange={e => set({ start_date: e.target.value })}/></label>
          {form.group_code === "BUILDING_PERMANENT" && <label className="text-sm">Actual life months (optional)<input type="number" min={240} max={1200} step={12} className={field} value={form.useful_life_months ?? ""} onChange={e => set({ useful_life_months: e.target.value ? Number(e.target.value) : null })}/></label>}
          <label className="text-sm">Fiscal opening date (optional year end)<input type="date" className={field} value={form.opening_date ?? ""} onChange={e => set({ opening_date: e.target.value || null })}/></label>
          <label className="text-sm">Fiscal opening value<input type="number" min="0" step="0.01" className={field} value={form.opening_book_value ?? ""} onChange={e => set({ opening_book_value: e.target.value || null })}/></label>
        </>}
        <label className="text-sm md:col-span-3">Classification / tax reference<input className={field} maxLength={500} value={form.reference} onChange={e => set({ reference: e.target.value })}/></label>
        <div className="flex gap-2"><Button type="submit" disabled={save.isPending}>Save fiscal profile</Button><Button type="button" variant="outline" onClick={() => setForm(null)}>Cancel</Button></div>
      </form>}
      {!!q.data?.schedule?.length && <details className="text-sm"><summary>Monthly fiscal schedule</summary><div className="max-h-64 overflow-auto"><table className="w-full text-right tabular-nums"><thead className="sticky top-0 bg-white"><tr><th className="text-left">Period</th><th>Opening</th><th>Depreciation</th><th>Closing</th></tr></thead><tbody>{q.data.schedule.map((r: any) => <tr key={r.period}><td className="text-left">{r.period}</td>{["opening", "depreciation", "closing"].map(k => <td key={k}>{Number(r[k]).toLocaleString("id-ID", { minimumFractionDigits: 2 })}</td>)}</tr>)}</tbody></table></div></details>}
    </>}
  </section>;
}
