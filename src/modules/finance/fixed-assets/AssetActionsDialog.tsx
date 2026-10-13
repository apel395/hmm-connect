import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Button from "@/components/ui/Button";
import { filterBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { todayLocal } from "@/utils/dateConstraints";
import { assetAction } from "./api";

export type AssetAction = "capitalize" | "transfer" | "dispose" | "write-off";
const titles = { capitalize: "Capitalize", transfer: "Transfer", dispose: "Dispose", "write-off": "Write Off" };
const input = "mt-1 block h-9 w-full rounded border px-2 text-sm";

export default function AssetActionsDialog({ asset, action, onClose }: { asset: any; action: AssetAction; onClose: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ date: todayLocal(), depreciation_start_date: "", business_unit_id: String(asset.business_unit_id || ""), location_id: String(asset.location_id || ""), department_id: String(asset.department_id || ""), create_journal: action === "transfer", offset_account_id: "", disposal_proceeds: "0", cash_account_id: "", reason: "", notes: "" });
  const set = (key: string, value: string | boolean) => setForm(current => ({ ...current, [key]: value }));
  const units = useQuery({ queryKey: ["asset-action-units"], queryFn: () => filterBusinessUnits({ is_active: true }), enabled: action === "transfer" });
  const locations = useQuery({ queryKey: ["asset-action-locations", form.business_unit_id], queryFn: () => listLocations({ business_unit_id: Number(form.business_unit_id), is_active: true }), enabled: action === "transfer" && Boolean(form.business_unit_id) });
  const departments = useQuery({ queryKey: ["asset-action-departments", form.business_unit_id, form.location_id], queryFn: () => listDepartments({ business_unit_id: Number(form.business_unit_id), location_id: Number(form.location_id) || undefined, is_active: true }), enabled: action === "transfer" && Boolean(form.business_unit_id) });
  const accounts = useQuery({ queryKey: ["asset-action-accounts"], queryFn: () => getAllAccountLookup({ is_active: true, is_posting: true }), enabled: action === "dispose" || action === "capitalize" });
  const submit = useMutation({
    mutationFn: () => {
      const payload = action === "capitalize" ? { capitalization_date: form.date, depreciation_start_date: asset.depreciation_method === "NONE" ? null : form.depreciation_start_date || null, create_journal: form.create_journal, offset_account_id: Number(form.offset_account_id) || null }
        : action === "transfer" ? { movement_date: form.date, business_unit_id: Number(form.business_unit_id), location_id: Number(form.location_id) || null, department_id: Number(form.department_id) || null, create_journal: form.create_journal, notes: form.notes }
        : action === "dispose" ? { disposal_date: form.date, disposal_proceeds: Number(form.disposal_proceeds), cash_account_id: Number(form.cash_account_id) || null, reason: form.reason, notes: form.notes }
        : { write_off_date: form.date, reason: form.reason, notes: form.notes };
      return assetAction(asset.id, action, payload);
    },
    onSuccess: () => { qc.invalidateQueries({ queryKey: ["fixed-asset", asset.id] }); qc.invalidateQueries({ queryKey: ["fixed-assets"] }); qc.invalidateQueries({ queryKey: ["depreciation-runs"] }); toast.success(`${titles[action]} completed`); onClose(); },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Action could not be completed"),
  });
  const sourcePosted = Boolean(asset.purchase_invoice_id || asset.goods_receipt_id || Number(asset.accumulated_depreciation));
  return <Dialog open onOpenChange={open => !open && !submit.isPending && onClose()}><DialogContent><DialogHeader><DialogTitle>{titles[action]} · {asset.asset_number}</DialogTitle></DialogHeader><DialogBody>
    <div className="grid gap-3 text-sm md:grid-cols-2">
      <label>Date<input type="date" data-accounting-date="true" className={input} value={form.date} onChange={event => set("date", event.target.value)} /></label>
      {action === "capitalize" && <>
        {asset.depreciation_method !== "NONE" && <label>Depreciation Start<input type="date" className={input} value={form.depreciation_start_date} onChange={event => set("depreciation_start_date", event.target.value)} /></label>}
        {!sourcePosted && <label className="flex items-center gap-2"><input type="checkbox" checked={form.create_journal} onChange={event => set("create_journal", event.target.checked)} />Post acquisition journal</label>}
        {form.create_journal && <label>Acquisition Credit Account<select className={input} value={form.offset_account_id} onChange={event => set("offset_account_id", event.target.value)}><option value="">Select account</option>{accounts.data?.filter(a => a.id !== asset.asset_account_id).map(a => <option key={a.id} value={a.id}>{a.account_code} — {a.account_name}</option>)}</select></label>}
      </>}
      {action === "transfer" && <>
        <label>Business Unit<select className={input} value={form.business_unit_id} onChange={event => setForm({ ...form, business_unit_id: event.target.value, location_id: "", department_id: "" })}><option value="">Select</option>{units.data?.map(u => <option key={u.id} value={u.id}>{u.name}</option>)}</select></label>
        <label>Location<select className={input} value={form.location_id} onChange={event => setForm({ ...form, location_id: event.target.value, department_id: "" })}><option value="">Optional</option>{locations.data?.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}</select></label>
        <label>Department<select className={input} value={form.department_id} onChange={event => set("department_id", event.target.value)}><option value="">Optional</option>{departments.data?.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
        <label className="flex items-center gap-2"><input type="checkbox" checked={form.create_journal} onChange={event => set("create_journal", event.target.checked)} />Reclassify ledger dimensions</label>
        <p className="md:col-span-2">Transfers the whole asset record{asset.quantity ? ` (${asset.quantity} units)` : ""}.</p>
      </>}
      {action === "dispose" && <>
        <label>Proceeds<input type="number" min={0} step="0.01" className={input} value={form.disposal_proceeds} onChange={event => set("disposal_proceeds", event.target.value)} /></label>
        {Number(form.disposal_proceeds) > 0 && <label>Cash / Bank<select className={input} value={form.cash_account_id} onChange={event => set("cash_account_id", event.target.value)}><option value="">Select</option>{accounts.data?.filter(a => a.account_type === "ASSET" && a.normal_balance === "DEBIT" && ["CASH", "BANK", "PETTY_CASH", "CASH_AND_BANK"].includes(a.account_subtype || "")).map(a => <option key={a.id} value={a.id}>{a.account_code} — {a.account_name}</option>)}</select></label>}
      </>}
      {(action === "dispose" || action === "write-off") && <label>Reason<input className={input} value={form.reason} onChange={event => set("reason", event.target.value)} /></label>}
      {action !== "capitalize" && <label className="md:col-span-2">Notes<input className={input} value={form.notes} onChange={event => set("notes", event.target.value)} /></label>}
    </div>
  </DialogBody><DialogFooter><Button variant="outline" disabled={submit.isPending} onClick={onClose}>Cancel</Button><Button loading={submit.isPending} disabled={!form.date || (action === "capitalize" && asset.depreciation_method !== "NONE" && !form.depreciation_start_date) || (action === "transfer" && !form.business_unit_id)} onClick={() => submit.mutate()}>{titles[action]}</Button></DialogFooter></DialogContent></Dialog>;
}
