import { useMemo, useState } from "react";
import Button from "@/components/ui/Button";

interface PurchaseRequisitionOption {
  id: number;
  pr_number: string;
  request_date?: string;
  required_date?: string;
  requester_name?: string;
  business_unit_id?: number | null;
  business_unit_name?: string | null;
  department_id?: number | null;
  department_name?: string | null;
  location_id?: number | null;
  location_name?: string | null;
  notes?: string | null;
  items?: Array<{ product_name?: string; remaining_quantity?: number; quantity?: number }>;
}

interface Props {
  options: PurchaseRequisitionOption[];
  selected: PurchaseRequisitionOption[];
  disabled?: boolean;
  onChange: (selected: PurchaseRequisitionOption[]) => void;
}

const sameOrganization = (left: PurchaseRequisitionOption, right: PurchaseRequisitionOption) =>
  left.business_unit_id === right.business_unit_id &&
  left.department_id === right.department_id &&
  left.location_id === right.location_id;

const itemSummary = (pr: PurchaseRequisitionOption) => {
  const items = (pr.items ?? []).filter((item) => Number(item.remaining_quantity ?? item.quantity ?? 0) > 0);
  if (!items.length) return "No remaining items";
  const names = items.slice(0, 2).map((item) => item.product_name || "Item").join(", ");
  return items.length > 2 ? `${names} +${items.length - 2} more` : names;
};

export default function PurchaseRequisitionPicker({ options, selected, disabled = false, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const selectedIds = useMemo(() => new Set(selected.map((item) => item.id)), [selected]);
  const anchor = selected[0];
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return options;
    return options.filter((pr) => [
      pr.pr_number, pr.requester_name, pr.department_name, pr.location_name, pr.notes,
      ...(pr.items ?? []).map((item) => item.product_name),
    ].filter(Boolean).join(" ").toLowerCase().includes(needle));
  }, [options, query]);

  const toggle = (pr: PurchaseRequisitionOption) => {
    if (selectedIds.has(pr.id)) {
      onChange(selected.filter((item) => item.id !== pr.id));
      return;
    }
    if (anchor && !sameOrganization(anchor, pr)) return;
    onChange([...selected, pr]);
  };

  return <div className="md:col-span-2">
    <div className="mb-1 text-sm font-medium">Approved Purchase Requisition</div>
    <button type="button" disabled={disabled} onClick={() => setOpen(true)} className="flex min-h-10 w-full items-center justify-between rounded-md border border-slate-300 bg-white px-3 py-2 text-left text-sm disabled:bg-slate-100">
      <span className={selected.length ? "text-slate-900" : "text-slate-400"}>{selected.length ? `${selected.length} PR selected: ${selected.map((pr) => pr.pr_number).join(", ")}` : "Search and select approved PRs..."}</span>
      <span className="ml-3 whitespace-nowrap text-xs font-semibold text-emerald-700">Browse PR</span>
    </button>
    {open && !disabled && <div className="fixed inset-0 z-[10001] flex items-center justify-center bg-slate-950/40 p-4" onMouseDown={(event) => event.target === event.currentTarget && setOpen(false)}>
      <div role="dialog" aria-modal="true" aria-label="Select purchase requisitions" className="flex max-h-[82vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl bg-white shadow-2xl">
        <div className="flex items-center justify-between border-b px-5 py-4"><div><div className="text-lg font-semibold">Select Approved PR</div><div className="text-xs text-slate-500">You may combine PRs only when Business Unit, department, and location match.</div></div><button type="button" className="text-2xl text-slate-500" aria-label="Close" onClick={() => setOpen(false)}>×</button></div>
        <div className="border-b p-4"><input autoFocus value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search PR number, item, requester, department, location, or notes..." className="h-10 w-full rounded-md border border-slate-300 px-3 text-sm" /></div>
        <div className="flex-1 overflow-auto"><table className="w-full min-w-[850px] text-sm"><thead className="sticky top-0 bg-slate-50"><tr><th className="w-12 p-3"/><th className="p-3 text-left">PR Number / Date</th><th className="p-3 text-left">Requester</th><th className="p-3 text-left">Organization</th><th className="p-3 text-left">Remaining Items</th></tr></thead><tbody>
          {filtered.map((pr) => { const incompatible = Boolean(anchor && !selectedIds.has(pr.id) && !sameOrganization(anchor, pr)); return <tr key={pr.id} className={`border-t ${incompatible ? "bg-slate-50 text-slate-400" : "hover:bg-emerald-50"}`}>
            <td className="p-3 text-center"><input type="checkbox" checked={selectedIds.has(pr.id)} disabled={incompatible} onChange={() => toggle(pr)} aria-label={`Select ${pr.pr_number}`} /></td>
            <td className="p-3"><div className="font-semibold">{pr.pr_number}</div><div className="text-xs text-slate-500">{pr.request_date ?? "—"} · needed {pr.required_date ?? "—"}</div></td>
            <td className="p-3">{pr.requester_name ?? "—"}</td>
            <td className="p-3"><div>{pr.location_name ?? "—"}</div><div className="text-xs text-slate-500">{pr.business_unit_name ?? "—"} · {pr.department_name ?? "—"}</div>{incompatible && <div className="mt-1 text-xs text-amber-700">Different organization</div>}</td>
            <td className="p-3">{itemSummary(pr)}</td>
          </tr>; })}
          {!filtered.length && <tr><td colSpan={5} className="p-8 text-center text-slate-500">No matching approved PR.</td></tr>}
        </tbody></table></div>
        <div className="flex items-center justify-between border-t px-5 py-4"><span className="text-sm text-slate-600">{selected.length} PR selected</span><div className="flex gap-2"><Button type="button" variant="secondary" onClick={() => onChange([])}>Clear</Button><Button type="button" onClick={() => setOpen(false)}>Use Selected PR</Button></div></div>
      </div>
    </div>}
  </div>;
}
