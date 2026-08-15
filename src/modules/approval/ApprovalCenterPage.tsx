import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CheckCircle2, Clock3, FileCheck2, XCircle } from "lucide-react";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import Badge from "@/components/ui/Badge";
import { approvalApi, approvalDocumentPath, type ApprovalRequestRow } from "./api";

const PAGE_SIZE = 20;
const views = [
  { key: "pending", label: "My Pending", icon: Clock3 },
  { key: "submitted", label: "My Submitted", icon: FileCheck2 },
  { key: "completed", label: "Completed", icon: CheckCircle2 },
  { key: "rejected", label: "Rejected", icon: XCircle },
] as const;

const entityLabel = (value: string) => value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function ApprovalCenterPage() {
  const qc = useQueryClient();
  const [view, setView] = useState<(typeof views)[number]["key"]>("pending");
  const [page, setPage] = useState(1);
  const [decision, setDecision] = useState<{ row: ApprovalRequestRow; action: "APPROVE" | "REJECT" } | null>(null);
  const [comment, setComment] = useState("");
  const inbox = useQuery({
    queryKey: ["approval-inbox", view, page],
    queryFn: () => approvalApi.inbox(view, page, PAGE_SIZE),
    placeholderData: (previous) => previous,
  });
  const rows = inbox.data?.items ?? [];
  const pendingCount = view === "pending" ? (inbox.data?.total_items ?? 0) : 0;

  const act = useMutation({
    mutationFn: async () => {
      if (!decision) return;
      if (decision.row.status !== "PENDING" || !decision.row.can_decide) throw new Error("This approval is no longer pending.");
      if (decision.action === "REJECT" && !comment.trim()) throw new Error("Rejection reason is required.");
      return decision.action === "APPROVE"
        ? approvalApi.approveDocument(decision.row, comment.trim() || undefined)
        : approvalApi.rejectDocument(decision.row, comment.trim());
    },
    onSuccess: () => {
      toast.success(decision?.action === "APPROVE" ? "Approval recorded." : "Document rejected.");
      setDecision(null);
      setComment("");
      qc.invalidateQueries({ queryKey: ["approval-inbox"] });
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || error?.message || "Approval action failed."),
  });

  const changeView = (next: (typeof views)[number]["key"]) => {
    setView(next);
    setPage(1);
  };

  return <div className="space-y-5">
    <PageHeader title="Approval Center" description="One inbox for approval work across purchasing, finance, and future business modules." />
    <Card className="p-0 overflow-hidden">
      <div className="flex min-w-max gap-6 overflow-x-auto border-b px-4 pt-3">
        {views.map((item) => { const Icon = item.icon; const active = item.key === view; return <button key={item.key} onClick={() => changeView(item.key)} className={`relative flex items-center gap-2 px-1 pb-3 text-sm font-medium ${active ? "text-[#086B5A]" : "text-slate-500 hover:text-slate-900"}`}><Icon className="h-4 w-4"/>{item.label}{item.key === "pending" && pendingCount > 0 && <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-xs text-emerald-800">{pendingCount}</span>}{active && <span className="absolute inset-x-0 bottom-0 h-0.5 bg-[#086B5A]"/>}</button> })}
      </div>
      {inbox.isLoading ? <div className="p-10 text-center text-sm text-slate-500">Loading approvals…</div> : inbox.isError ? <div className="p-10 text-center text-sm text-red-600">Approval inbox could not be loaded.</div> : !rows.length ? <div className="p-10 text-center text-sm text-slate-500">No approval items in this view.</div> : <div className="overflow-x-auto"><table className="min-w-[1000px] w-full text-sm"><thead className="bg-slate-50 text-left text-xs uppercase text-slate-500"><tr><th className="p-3">Document</th><th className="p-3">Workflow</th><th className="p-3">Current Stage</th><th className="p-3">Submitted By</th><th className="p-3">Status</th><th className="p-3 text-right">Action</th></tr></thead><tbody className="divide-y">{rows.map((row) => { const path = approvalDocumentPath(row); const canDecide = row.status === "PENDING" && row.can_decide && row.current_stage.length > 0; return <tr key={row.id}><td className="p-3"><div className="font-medium">{entityLabel(row.entity_type)} #{row.entity_id}</div>{path && <Link to={path} className="text-xs text-emerald-700 hover:underline">Open document</Link>}</td><td className="p-3">{row.workflow_name}</td><td className="p-3">{row.current_stage.length ? row.current_stage.join(" + ") : "—"}</td><td className="p-3">{row.created_by_name || "—"}</td><td className="p-3"><Badge variant={row.status === "APPROVED" ? "success" : row.status === "REJECTED" ? "danger" : "warning"}>{row.status}</Badge></td><td className="p-3"><div className="flex justify-end gap-2">{canDecide && <><Button size="sm" onClick={() => { setDecision({ row, action: "APPROVE" }); setComment(""); }}>Approve</Button><Button size="sm" variant="danger" onClick={() => { setDecision({ row, action: "REJECT" }); setComment(""); }}>Reject</Button></>}</div></td></tr> })}</tbody></table></div>}
      {!inbox.isLoading && !inbox.isError && (inbox.data?.total_pages ?? 0) > 1 && <div className="flex items-center justify-between border-t px-4 py-3"><span className="text-sm text-slate-500">{inbox.data?.total_items ?? 0} approval item{(inbox.data?.total_items ?? 0) === 1 ? "" : "s"}</span><div className="flex items-center gap-3"><Button size="sm" variant="outline" disabled={!inbox.data?.has_previous} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</Button><span className="text-sm">Page {inbox.data?.page} of {inbox.data?.total_pages}</span><Button size="sm" variant="outline" disabled={!inbox.data?.has_next} onClick={() => setPage((value) => value + 1)}>Next</Button></div></div>}
    </Card>

    <Dialog open={Boolean(decision)} onOpenChange={(open) => !open && setDecision(null)}><DialogContent><DialogHeader><DialogTitle>{decision?.action === "APPROVE" ? "Approve Document" : "Reject Document"}</DialogTitle></DialogHeader><DialogBody><label className="block text-sm font-medium">Comment {decision?.action === "REJECT" ? "*" : ""}<textarea className="mt-2 min-h-28 w-full rounded-md border border-slate-300 p-3 text-sm" value={comment} onChange={(event) => setComment(event.target.value)} placeholder={decision?.action === "REJECT" ? "Reason for rejection" : "Optional approval comment"}/></label></DialogBody><DialogFooter><Button variant="outline" onClick={() => setDecision(null)}>Cancel</Button><Button variant={decision?.action === "REJECT" ? "danger" : "primary"} loading={act.isPending} disabled={decision?.action === "REJECT" && !comment.trim()} onClick={() => act.mutate()}>{decision?.action === "REJECT" ? "Reject" : "Approve"}</Button></DialogFooter></DialogContent></Dialog>
  </div>;
}
