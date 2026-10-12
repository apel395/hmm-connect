import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { storeRequestApi } from "./api";
import type { StoreRequest, StoreRequestItem } from "./types";

const qty = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });

export default function StoreRequestDetailPage() {
  const { id } = useParams();
  const requestId = Number(id);
  const qc = useQueryClient();
  const [rejectReason, setRejectReason] = useState("");
  const [showIssue, setShowIssue] = useState(false);
  const [issueDate, setIssueDate] = useState(() => new Date().toLocaleDateString("en-CA", {timeZone:"Asia/Jakarta"}));
  const [issueNotes, setIssueNotes] = useState("");
  const [issueQty, setIssueQty] = useState<Record<number, number>>({});

  const query = useQuery({ queryKey: ["store-request", requestId], queryFn: async () => (await storeRequestApi.detail(requestId)).data, enabled: Number.isFinite(requestId) });
  const request = query.data as StoreRequest | undefined;
  const refresh = async () => { await qc.invalidateQueries({ queryKey: ["store-request", requestId] }); await qc.invalidateQueries({ queryKey: ["store-requests"] }); await qc.invalidateQueries({ queryKey: ["inventory"] }); };
  const submit = useMutation({ mutationFn: () => storeRequestApi.submit(requestId), onSuccess: refresh });
  const approve = useMutation({ mutationFn: () => storeRequestApi.approve(requestId), onSuccess: refresh });
  const reject = useMutation({ mutationFn: () => storeRequestApi.reject(requestId, rejectReason), onSuccess: async () => { setRejectReason(""); await refresh(); } });
  const createIssue = useMutation({
    mutationFn: () => {
      const sourceItems = request?.items ?? [];
      const invalid = sourceItems.find((item) => {
        const quantity = Number(issueQty[item.id] ?? 0);
        return quantity > Math.min(Number(item.remaining_quantity), Number(item.available_stock));
      });
      if (invalid) throw new Error(`Issue quantity for ${invalid.product_name} exceeds remaining or available stock`);
      const items = sourceItems.map((item) => ({ item_id: item.id, quantity: Number(issueQty[item.id] ?? 0) })).filter((item) => item.quantity > 0);
      if (!items.length) throw new Error("Enter at least one Issue Now quantity");
      return storeRequestApi.createIssue(requestId, { items, issue_date: issueDate, notes: issueNotes || null });
    },
    onSuccess: async () => { setShowIssue(false); setIssueQty({}); setIssueNotes(""); await refresh(); },
  });
  const postIssue = useMutation({ mutationFn: (issueId: number) => storeRequestApi.postIssue(issueId), onSuccess: refresh });

  const itemRows = request?.items ?? [];
  const hasDraftIssue = useMemo(() => (request?.issues ?? []).some((issue) => issue.status === "DRAFT"), [request?.issues]);
  const hasRequestItems = itemRows.length > 0;
  const hasRemainingItems = itemRows.some((item) => Number(item.remaining_quantity) > 0);

  if (query.isLoading) return <div className="p-6 text-sm text-slate-500">Loading Store Request...</div>;
  if (!request) return <div className="p-6 text-sm text-red-600">Store Request not found.</div>;

  return <div className="space-y-6">
    <div className="flex flex-wrap items-start justify-between gap-4"><div><Link className="text-sm text-emerald-700" to="/store-requests">← Store Requests</Link><h1 className="mt-2 text-2xl font-semibold">{request.sr_number}</h1><div className="mt-1 text-sm text-slate-500">{request.status.replaceAll("_", " ")} · {request.request_date}</div></div><div className="flex flex-wrap gap-2">{request.allowed_actions?.can_submit && <Button disabled={submit.isPending} onClick={() => submit.mutate()}>Submit</Button>}{request.allowed_actions?.can_approve && <Button disabled={approve.isPending} onClick={() => approve.mutate()}>Approve</Button>}{request.allowed_actions?.can_issue && hasRequestItems && hasRemainingItems && !hasDraftIssue && <Button onClick={() => setShowIssue(true)}>Create Issue</Button>}<Link className="inline-flex h-10 items-center rounded-md border border-slate-300 px-4 text-sm font-medium" to={`/store-requests/${request.id}/print`}>Print</Link></div></div>

    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><Card className="p-4"><div className="text-xs uppercase text-slate-500">Business Unit</div><div className="mt-1 font-medium">{request.business_unit_name ?? "—"}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Department</div><div className="mt-1 font-medium">{request.department_name ?? "—"}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Location</div><div className="mt-1 font-medium">{request.location_name ?? "—"}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Warehouse</div><div className="mt-1 font-medium">{request.warehouse_name ?? "—"}</div></Card></div>

    {!hasRequestItems && <Card className="border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">This Store Request contains no requested items. Submit, approval completion, and Goods Issue creation are blocked. Create a new Store Request with at least one positive-quantity item.</Card>}

    <Card className="p-0"><div className="border-b px-4 py-3"><h2 className="font-semibold">Requested Items</h2></div><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-xs"><thead><tr><th className="px-4 py-3 text-left">Code</th><th className="px-4 py-3 text-left">Item</th><th className="px-4 py-3 text-right">Requested</th><th className="px-4 py-3 text-right">Issued</th><th className="px-4 py-3 text-right">Remaining</th><th className="px-4 py-3 text-right">Available</th><th className="px-4 py-3 text-left">UOM</th></tr></thead><tbody>{itemRows.map((item) => <tr key={item.id} className="border-t whitespace-nowrap"><td className="px-4 py-3">{item.product_code}</td><td className="px-4 py-3 font-medium">{item.product_name}</td><td className="px-4 py-3 text-right">{qty(item.requested_quantity)}</td><td className="px-4 py-3 text-right">{qty(item.issued_quantity)}</td><td className="px-4 py-3 text-right font-semibold">{qty(item.remaining_quantity)}</td><td className={`px-4 py-3 text-right ${Number(item.available_stock) < Number(item.remaining_quantity) ? "text-amber-700" : ""}`}>{qty(item.available_stock)}</td><td className="px-4 py-3">{item.uom}</td></tr>)}</tbody></table></div></Card>

    {request.allowed_actions?.can_reject && <Card className="p-4"><div className="flex flex-col gap-3 md:flex-row"><input className="h-10 flex-1 rounded-md border border-slate-300 px-3 text-sm" placeholder="Rejection reason" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} /><Button variant="secondary" disabled={!rejectReason.trim() || reject.isPending} onClick={() => reject.mutate()}>Reject</Button></div></Card>}

    <Card className="p-0"><div className="border-b px-4 py-3"><h2 className="font-semibold">Issue History</h2></div>{(request.issues ?? []).length ? <div className="divide-y">{(request.issues ?? []).map((issue) => <div key={issue.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"><div><div className="font-medium">{issue.issue_number}</div><div className="text-xs text-slate-500">{issue.status} · {issue.issue_date ?? "—"} · {new Date(issue.posted_at ?? issue.created_at).toLocaleString()} · {issue.items.map((item) => `${item.product_code} ${qty(item.quantity)} ${item.uom}`).join(", ")}</div></div>{issue.status === "DRAFT" && request.allowed_actions?.can_issue && <Button disabled={postIssue.isPending} onClick={() => postIssue.mutate(issue.id)}>Post Issue</Button>}</div>)}</div> : <div className="p-6 text-sm text-slate-500">No goods issues yet.</div>}</Card>

    {showIssue && <IssueDialog items={itemRows} values={issueQty} notes={issueNotes} issueDate={issueDate} onIssueDate={setIssueDate} onChange={setIssueQty} onNotes={setIssueNotes} onClose={() => setShowIssue(false)} onSave={() => createIssue.mutate()} saving={createIssue.isPending} error={createIssue.error} />}
  </div>;
}

function IssueDialog({ items, values, notes, issueDate, onIssueDate, onChange, onNotes, onClose, onSave, saving, error }: { issueDate: string; onIssueDate: (value: string) => void; items: StoreRequestItem[]; values: Record<number, number>; notes: string; onChange: (value: Record<number, number>) => void; onNotes: (value: string) => void; onClose: () => void; onSave: () => void; saving: boolean; error: unknown }) {
  const eligibleItems = items.filter((item) => Number(item.remaining_quantity) > 0);
  const hasIssueQuantity = eligibleItems.some((item) => Number(values[item.id] ?? 0) > 0);
  return <div className="fixed inset-0 z-[80] grid place-items-center bg-black/40 p-4"><div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl"><div className="mb-5 flex items-center justify-between"><div><h2 className="text-lg font-semibold">Create Goods Issue</h2><p className="text-xs text-slate-500">Create a draft first. Stock changes only when the issue is posted.</p></div><Button variant="secondary" onClick={onClose}>Close</Button></div><label className="mb-3 block text-sm">Warehouse issue date<input type="date" data-accounting-date="true" value={issueDate} onChange={e=>onIssueDate(e.target.value)} className="ml-3 rounded border px-2 py-1" /></label><div className="overflow-x-auto"><table className="w-full min-w-[720px] text-xs"><thead><tr><th className="py-2 text-left">Item</th><th className="py-2 text-right">Requested</th><th className="py-2 text-right">Previously Issued</th><th className="py-2 text-right">Remaining</th><th className="py-2 text-right">Available</th><th className="py-2 text-right">Issue Now</th></tr></thead><tbody>{eligibleItems.map((item) => <tr key={item.id} className="border-t"><td className="py-3"><div className="font-medium">{item.product_name}</div><div className="text-[11px] text-slate-500">{item.product_code} · {item.uom}</div></td><td className="py-3 text-right">{qty(item.requested_quantity)}</td><td className="py-3 text-right">{qty(item.issued_quantity)}</td><td className="py-3 text-right font-medium">{qty(item.remaining_quantity)}</td><td className="py-3 text-right">{qty(item.available_stock)}</td><td className="py-3 pl-4"><input className="h-9 w-28 rounded border border-slate-300 px-2 text-right" type="number" min="0" max={Math.min(Number(item.remaining_quantity), Number(item.available_stock))} step="0.01" value={values[item.id] ?? ""} onChange={(e) => onChange({ ...values, [item.id]: Number(e.target.value) })} /></td></tr>)}</tbody></table></div><textarea className="mt-4 min-h-20 w-full rounded-md border border-slate-300 p-3 text-sm" placeholder="Issue notes" value={notes} onChange={(e) => onNotes(e.target.value)} />{Boolean(error) && <div className="mt-3 text-sm text-red-600">{error instanceof Error ? error.message : "Unable to create goods issue"}</div>}<div className="mt-5 flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={saving || !hasIssueQuantity} onClick={onSave}>{saving ? "Saving..." : "Create Issue Draft"}</Button></div></div></div>;
}
