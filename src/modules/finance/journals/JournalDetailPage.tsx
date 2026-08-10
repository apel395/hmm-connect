import { ArrowLeft } from "lucide-react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Loading from "@/components/ui/Loading";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import { getJournal, journalAction } from "./api";

export default function JournalDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["journal-entry", id], queryFn: () => getJournal(Number(id)), enabled: !!id });
  const act = useMutation({
    mutationFn: (action: string) => journalAction(Number(id), action),
    onSuccess: (_, action) => {
      toast.success(action === "unpost" ? "Journal returned to draft." : `Journal ${action}ed.`);
      qc.invalidateQueries({ queryKey: ["journal-entry", id] });
      qc.invalidateQueries({ queryKey: ["journal-entries"] });
      qc.invalidateQueries({ queryKey: ["general-ledger"] });
      qc.invalidateQueries({ queryKey: ["trial-balance"] });
      qc.invalidateQueries({ queryKey: ["accounts-payable-aging"] });
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Journal action failed."),
  });
  if (q.isLoading) return <Loading/>;
  if (!q.data) return <p>Journal not found.</p>;
  const x = q.data;
  const a = x.allowed_actions;
  return <div className="space-y-6">
    <div className="flex flex-wrap justify-between gap-3">
      <div className="flex items-center gap-3"><Button variant="outline" onClick={() => nav("/journal")}><ArrowLeft size={16}/> Back</Button><h1 className="text-2xl font-bold">{x.journal_number}</h1><Badge>{x.status}</Badge></div>
      <div className="flex flex-wrap gap-2">
        <PrintPreviewButton src={`/journal-entries/${x.id}/print`} title={`Journal ${x.journal_number}`} ariaLabel="Preview journal" />
        {a.can_edit && <Button variant="outline">Edit</Button>}
        {a.can_post && <Button loading={act.isPending} onClick={() => act.mutate("post")}>Post</Button>}
        {a.can_unpost && <Button loading={act.isPending} variant="outline" onClick={() => act.mutate("unpost")}>Unpost</Button>}
        {a.can_void && <Button variant="danger" loading={act.isPending} onClick={() => act.mutate("void")}>Void</Button>}
      </div>
    </div>
    <Card><div className="grid gap-4 md:grid-cols-4"><div><small>Date</small><div>{x.journal_date}</div></div><div><small>Reference</small><div>{x.reference_number || "—"}</div></div><div><small>Description</small><div>{x.description || "—"}</div></div><div><small>Created By</small><div>{x.created_by_name || "—"}</div></div></div></Card>
    <Card className="overflow-x-auto"><table className="table-grid w-full text-sm"><thead><tr className="border-b text-left"><th className="p-3">Account Code</th><th>Account Name</th><th>Description</th><th className="text-right">Debit</th><th className="text-right">Credit</th><th>Department</th><th>Location</th></tr></thead><tbody>{x.lines.map((l: any) => <tr key={l.id} className="border-b"><td className="p-3">{l.account_code}</td><td>{l.account_name}</td><td>{l.description || "—"}</td><td className="text-right">{Number(l.debit).toLocaleString()}</td><td className="text-right">{Number(l.credit).toLocaleString()}</td><td>{l.department_name || "—"}</td><td>{l.location_name || "—"}</td></tr>)}</tbody></table></Card>
    <Card><div className="grid grid-cols-3 gap-4 text-right"><div><small>Total Debit</small><div className="text-lg font-bold">{Number(x.total_debit).toLocaleString()}</div></div><div><small>Total Credit</small><div className="text-lg font-bold">{Number(x.total_credit).toLocaleString()}</div></div><div><small>Difference</small><div className="text-lg font-bold">{Number(x.difference).toLocaleString()}</div></div></div></Card>
    {x.status === "POSTED" && !a.can_unpost && <p className="text-xs text-slate-500">This journal is controlled by its originating document and must be reversed there rather than unposted directly.</p>}
  </div>;
}
