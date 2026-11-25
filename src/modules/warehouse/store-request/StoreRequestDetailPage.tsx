import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import ModuleSummary from "@/components/common/ModuleSummary";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge, { type BadgeVariant } from "@/components/ui/Badge";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import { FORM_UI } from "@/config/formUi";
import { warehouseErrorMessage } from "../errors";
import { storeRequestApi } from "./api";
import type { StoreIssue, StoreRequest, StoreRequestItem, StoreRequestStatus } from "./types";

const qty = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });

const money = (value: number | string | null | undefined) => value == null ? "—" : Number(value).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const input = `${FORM_UI.controlBase} ${FORM_UI.density.standard.control}`;
const statusVariant: Record<StoreRequestStatus, BadgeVariant> = {
  DRAFT: "warning",
  PENDING_APPROVAL: "info",
  APPROVED: "success",
  PARTIALLY_ISSUED: "primary",
  ISSUED: "success",
  REJECTED: "danger",
};
const issueStatusVariant: Record<StoreIssue["status"], BadgeVariant> = { DRAFT: "warning", POSTED: "success" };

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
  const request: StoreRequest | undefined = query.data;
  const refresh = async () => { await qc.invalidateQueries({ queryKey: ["store-request", requestId] }); await qc.invalidateQueries({ queryKey: ["store-requests"] }); await qc.invalidateQueries({ queryKey: ["inventory"] }); };
  const submit = useMutation({ mutationFn: () => storeRequestApi.submit(requestId), onSuccess: refresh });
  const approve = useMutation({ mutationFn: () => storeRequestApi.approve(requestId), onSuccess: refresh });
  const reject = useMutation({ mutationFn: () => storeRequestApi.reject(requestId, rejectReason), onSuccess: async () => { setRejectReason(""); await refresh(); } });
  const createIssue = useMutation({
    mutationFn: () => {
      if (!issueDate || (request && issueDate < request.request_date)) throw new Error("Issue date cannot precede the request date");
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
  const actionErrors: unknown[] = [submit.error, approve.error, reject.error, postIssue.error].filter(Boolean);

  if (query.isLoading) return <DataWorkspace area="Inventory">
    <PageHeader title="Store Request" description="Internal warehouse stock requests and goods issue tracking." actions={<WorkspaceBackButton />} />
    <Loading message="Loading Store Request..." />
  </DataWorkspace>;
  if (query.isError) return <DataWorkspace area="Inventory">
    <PageHeader title="Store Request" description="Internal warehouse stock requests and goods issue tracking." actions={<WorkspaceBackButton />} />
    <p role="alert" className="text-sm text-red-700">{warehouseErrorMessage(query.error, "Store Request could not be loaded.")}</p>
  </DataWorkspace>;
  if (!request) return <DataWorkspace area="Inventory">
    <PageHeader title="Store Request" description="Internal warehouse stock requests and goods issue tracking." actions={<WorkspaceBackButton />} />
    <Empty title="Store Request not found." description="Choose a store request from the list to see its details." />
  </DataWorkspace>;

  return <DataWorkspace area="Inventory">
    <div className="space-y-6">
      <PageHeader title={request.sr_number} description="Internal warehouse stock requests and goods issue tracking." actions={<>
        <WorkspaceBackButton />
        {request.allowed_actions?.can_submit && <Button disabled={submit.isPending} onClick={() => submit.mutate()}>Submit</Button>}
        {request.allowed_actions?.can_approve && <Button disabled={approve.isPending} onClick={() => approve.mutate()}>Approve</Button>}
        {request.allowed_actions?.can_issue && hasRequestItems && hasRemainingItems && !hasDraftIssue && <Button onClick={() => setShowIssue(true)}>Create Issue</Button>}
        <Link className="inline-flex h-10 items-center rounded-md border border-slate-300 px-4 text-sm font-medium" to={`/store-requests/${request.id}/print`}>Print</Link>
      </>}>
        <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-500">
          <Link className="text-sm text-emerald-700" to="/store-requests">← Store Requests</Link>
          <span className="flex items-center gap-2"><Badge variant={statusVariant[request.status] ?? "default"}>{request.status.replaceAll("_", " ")}</Badge> · {request.request_date}</span>
        </div>
      </PageHeader>

      <ModuleSummary metrics={[
        { label: "Requested items", value: itemRows.length },
        { label: "Remaining qty", value: qty(itemRows.reduce((sum, item) => sum + Number(item.remaining_quantity ?? 0), 0)) },
        { label: "Estimated total", value: money(request.estimated_total) },
        { label: "Goods issues", value: (request.issues ?? []).length },
      ]} />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><Card className="p-4"><div className="text-xs uppercase text-slate-500">Business Unit</div><div className="mt-1 font-medium">{request.business_unit_name ?? "—"}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Department</div><div className="mt-1 font-medium">{request.department_name ?? "—"}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Location</div><div className="mt-1 font-medium">{request.location_name ?? "—"}</div></Card><Card className="p-4"><div className="text-xs uppercase text-slate-500">Warehouse</div><div className="mt-1 font-medium">{request.warehouse_name ?? "—"}</div></Card></div>

      {!hasRequestItems && <Card className="border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">This Store Request contains no requested items. Submit, approval completion, and Goods Issue creation are blocked. Create a new Store Request with at least one positive-quantity item.</Card>}

      <Card className="p-0"><div className="border-b px-4 py-3"><h2 className="font-semibold">Requested Items</h2><p className="text-xs text-slate-500">Reference: current warehouse average cost.</p></div><div className="overflow-x-auto"><table className="w-full min-w-[900px] text-xs"><thead><tr><th className="px-4 py-3 text-left">Code</th><th className="px-4 py-3 text-left">Item</th><th className="px-4 py-3 text-right">Requested</th><th className="px-4 py-3 text-right">Issued</th><th className="px-4 py-3 text-right">Remaining</th><th className="px-4 py-3 text-right">Available</th><th className="px-4 py-3 text-left">UOM</th><th className="px-4 py-3 text-right">Ref. Price</th><th className="px-4 py-3 text-right">Est. Value</th></tr></thead><tbody>
        {itemRows.length === 0 && <tr><td colSpan={9} className="px-4 py-10"><Empty title="No requested items" description="Add items when creating a store request." /></td></tr>}
        {itemRows.map((item) => <tr key={item.id} className="border-t whitespace-nowrap"><td className="px-4 py-3">{item.product_code}</td><td className="px-4 py-3 font-medium">{item.product_name}</td><td className="px-4 py-3 text-right">{qty(item.requested_quantity)}</td><td className="px-4 py-3 text-right">{qty(item.issued_quantity)}</td><td className="px-4 py-3 text-right font-semibold">{qty(item.remaining_quantity)}</td><td className={`px-4 py-3 text-right ${Number(item.available_stock) < Number(item.remaining_quantity) ? "text-amber-700" : ""}`}>{qty(item.available_stock)}</td><td className="px-4 py-3">{item.uom}</td><td className="px-4 py-3 text-right tabular-nums">{money(item.reference_unit_cost)}</td><td className="px-4 py-3 text-right tabular-nums">{money(item.estimated_value)}</td></tr>)}
      </tbody></table></div><div className="border-t px-4 py-2 text-right text-sm">Estimated total: <strong className="tabular-nums">{money(request.estimated_total)}</strong></div></Card>

      {request.allowed_actions?.can_reject && <Card className="p-4"><div className="flex flex-col gap-3 md:flex-row"><input className={`${input} flex-1`} placeholder="Rejection reason" value={rejectReason} onChange={(e) => setRejectReason(e.target.value)} /><Button variant="secondary" disabled={!rejectReason.trim() || reject.isPending} onClick={() => reject.mutate()}>Reject</Button></div></Card>}

      <Card className="p-0"><div className="border-b px-4 py-3"><h2 className="font-semibold">Issue History</h2></div>{(request.issues ?? []).length ? <div className="divide-y">{(request.issues ?? []).map((issue) => <div key={issue.id} className="flex flex-wrap items-center justify-between gap-3 px-4 py-3"><div><div className="font-medium">{issue.issue_number}</div><div className="text-xs text-slate-500"><Badge variant={issueStatusVariant[issue.status] ?? "default"}>{issue.status}</Badge> · {issue.issue_date ?? "—"} · {new Date(issue.posted_at ?? issue.created_at).toLocaleString()} · {issue.items.map((item) => `${item.product_code} ${qty(item.quantity)} ${item.uom}`).join(", ")}</div></div>{issue.status === "DRAFT" && request.allowed_actions?.can_issue && <Button disabled={postIssue.isPending} onClick={() => postIssue.mutate(issue.id)}>Post Issue</Button>}</div>)}</div> : <div className="p-6"><Empty title="No goods issues yet." description="Approved requests can create draft goods issues." /></div>}</Card>

      {actionErrors.map((error, i) => <p role="alert" key={i} className="text-sm text-red-700">{warehouseErrorMessage(error, "Action failed")}</p>)}
      {!!request.approval_history?.length && <Card className="overflow-x-auto p-2"><h2 className="mb-2 font-semibold">Store Approval</h2><table className="w-full text-xs"><thead><tr><th className="text-left">Step</th><th className="text-left">Approver</th><th className="text-left">Status</th><th className="text-left">Date / Time (WIB)</th></tr></thead><tbody>{request.approval_history.map(step => <tr key={step.level} className="border-t"><td className="py-1">{step.name}</td><td>{step.approver_name ?? step.approver_role}</td><td>{step.status}</td><td>{step.decided_at ? new Date(step.decided_at).toLocaleString("id-ID", {timeZone:"Asia/Jakarta"}) : "—"}</td></tr>)}</tbody></table></Card>}
      {showIssue && <IssueDialog items={itemRows} values={issueQty} notes={issueNotes} issueDate={issueDate} onIssueDate={setIssueDate} onChange={setIssueQty} onNotes={setIssueNotes} onClose={() => setShowIssue(false)} onSave={() => createIssue.mutate()} saving={createIssue.isPending} error={createIssue.error} />}
    </div>
  </DataWorkspace>;
}

function IssueDialog({ items, values, notes, issueDate, onIssueDate, onChange, onNotes, onClose, onSave, saving, error }: { issueDate: string; onIssueDate: (value: string) => void; items: StoreRequestItem[]; values: Record<number, number>; notes: string; onChange: (value: Record<number, number>) => void; onNotes: (value: string) => void; onClose: () => void; onSave: () => void; saving: boolean; error: unknown }) {
  const eligibleItems = items.filter((item) => Number(item.remaining_quantity) > 0);
  const hasIssueQuantity = eligibleItems.some((item) => Number(values[item.id] ?? 0) > 0);
  return <div className="fixed inset-0 z-[80] grid place-items-center bg-black/40 p-4"><div className="max-h-[90vh] w-full max-w-4xl overflow-y-auto rounded-xl bg-white p-6 shadow-xl"><div className="mb-5 flex items-center justify-between"><div><h2 className="text-lg font-semibold">Create Goods Issue</h2><p className="text-xs text-slate-500">Create a draft first. Stock changes only when the issue is posted.</p></div><Button variant="secondary" onClick={onClose}>Close</Button></div><label className="mb-3 block text-sm">Warehouse issue date<input required type="date" data-accounting-date="true" value={issueDate} onChange={e=>onIssueDate(e.target.value)} className={`${FORM_UI.controlBase} ${FORM_UI.density.compact.control} ml-3 w-auto`} /></label><div className="overflow-x-auto"><table className="w-full min-w-[720px] text-xs"><thead><tr><th className="py-2 text-left">Item</th><th className="py-2 text-right">Requested</th><th className="py-2 text-right">Previously Issued</th><th className="py-2 text-right">Remaining</th><th className="py-2 text-right">Available</th><th className="py-2 text-right">Issue Now</th></tr></thead><tbody>{eligibleItems.map((item) => <tr key={item.id} className="border-t"><td className="py-3"><div className="font-medium">{item.product_name}</div><div className="text-[11px] text-slate-500">{item.product_code} · {item.uom}</div></td><td className="py-3 text-right">{qty(item.requested_quantity)}</td><td className="py-3 text-right">{qty(item.issued_quantity)}</td><td className="py-3 text-right font-medium">{qty(item.remaining_quantity)}</td><td className="py-3 text-right">{qty(item.available_stock)}</td><td className="py-3 pl-4"><input className={`${input} w-28 text-right`} type="number" min="0" max={Math.min(Number(item.remaining_quantity), Number(item.available_stock))} step="0.01" value={values[item.id] ?? ""} onChange={(e) => onChange({ ...values, [item.id]: Number(e.target.value) })} /></td></tr>)}</tbody></table></div><textarea className={`${FORM_UI.controlBase} ${FORM_UI.density.standard.textarea} mt-4 w-full`} placeholder="Issue notes" value={notes} onChange={(e) => onNotes(e.target.value)} />{Boolean(error) && <div className="mt-3 text-sm text-red-600">{warehouseErrorMessage(error, "Unable to create goods issue")}</div>}<div className="mt-5 flex justify-end gap-2"><Button variant="secondary" onClick={onClose}>Cancel</Button><Button disabled={saving || !hasIssueQuantity} onClick={onSave}>{saving ? "Saving..." : "Create Issue Draft"}</Button></div></div></div>;
}
