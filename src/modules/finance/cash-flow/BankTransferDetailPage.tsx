import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import WorkspaceBackButton from "@/components/workspace/WorkspaceBackButton";
import useAuthorization from "@/hooks/useAuthorization";
import { useMutation,useQuery,useQueryClient } from "@tanstack/react-query";
import { Link,useNavigate,useParams } from "react-router-dom";
import { toast } from "sonner";
import { getTransfer,transferAction,updateTransfer } from "./api";

export default function BankTransferDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const { isSuperuser } = useAuthorization();
  const q = useQuery({ queryKey: ["bank-transfer", id], queryFn: () => getTransfer(Number(id)), enabled: !!id });
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["bank-transfer", id] });
    qc.invalidateQueries({ queryKey: ["bank-transfers"] });
    qc.invalidateQueries({ queryKey: ["cash-flow"] });
    qc.invalidateQueries({ queryKey: ["cash-accounts"] });
    qc.invalidateQueries({ queryKey: ["journal-entries"] });
    qc.invalidateQueries({ queryKey: ["general-ledger"] });
    qc.invalidateQueries({ queryKey: ["trial-balance"] });
  };
  const act = useMutation({ mutationFn: () => transferAction(Number(id), "generate-journal"), onSuccess: () => { toast.success("Draft journal created. Review and post it from Journal."); refresh(); }, onError: (e: any) => toast.error(e.response?.data?.detail || "Journal generation failed") });
  const edit = useMutation({ mutationFn: (payload: any) => updateTransfer(Number(id), payload), onSuccess: () => { toast.success("Transfer updated"); refresh(); }, onError: (e: any) => toast.error(e.response?.data?.detail || "Update failed") });
  if (q.isLoading) return <Loading />;
  const x = q.data;
  if (!x) return <p>Transfer not found.</p>;
  const admin = isSuperuser();
  const adminRecoverable = admin && x.status === "POSTED" && Boolean(x.journal_entry_id);
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap justify-between gap-3">
        <div className="flex items-center gap-3">
          <WorkspaceBackButton />
          <h1 className="text-2xl font-bold">{x.transfer_number}</h1><Badge>{x.status}</Badge>{admin && <Badge variant="outline">Admin</Badge>}
        </div>
        <div className="flex flex-wrap gap-2">
          <PrintPreviewButton src={`/bank-transfers/${x.id}/print`} title={`Bank Transfer ${x.transfer_number}`} ariaLabel="Preview bank transfer" />
          {x.allowed_actions.can_edit && <Button variant="outline" onClick={() => {
            const amount = window.prompt("Transfer amount", String(x.amount)); if (amount === null) return;
            const reference_number = window.prompt("Reference number", x.reference_number || ""); if (reference_number === null) return;
            const notes = window.prompt("Notes", x.notes || ""); if (notes === null) return;
            edit.mutate({ transfer_date: x.transfer_date, source_account_id: x.source_account_id, destination_account_id: x.destination_account_id, amount: Number(amount), currency: x.currency, reference_number, notes });
          }}>Edit</Button>}
          {x.allowed_actions.can_generate_journal && <Button onClick={() => act.mutate()}>Create Journal</Button>}
          {x.status === "DRAFT" && x.journal_entry_id && <Button onClick={() => nav(`/journal-entries/${x.journal_entry_id}`)}>Open Journal to Post</Button>}
          {adminRecoverable && <Button variant="outline" onClick={() => nav(`/journal-entries/${x.journal_entry_id}`)}>Admin Unpost / Correct</Button>}
        </div>
      </div>
      {x.status === "DRAFT" && x.journal_entry_id && <div className="rounded-md border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">The transfer journal is DRAFT. Posting is available only from the Journal page.</div>}
      {adminRecoverable && <div className="rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">Administrator recovery is available from the related journal. Safe unpost removes the transfer GL rows and returns this transfer to DRAFT. Closed fiscal periods remain locked.</div>}
      <Card>
        <div className="grid gap-4 md:grid-cols-4">
          <div><small>Date</small><div>{x.transfer_date}</div></div>
          <div><small>Source</small><div>{x.source_account_code} — {x.source_account_name}</div></div>
          <div><small>Destination</small><div>{x.destination_account_code} — {x.destination_account_name}</div></div>
          <div><small>Amount</small><div className="tabular-nums">{Number(x.amount).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})} {x.currency}</div></div>
          <div><small>Reference</small><div>{x.reference_number || "—"}</div></div>
          <div><small>Notes</small><div>{x.notes || "—"}</div></div>
        </div>
        {x.journal_entry_id && <p className="mt-4">Related Journal: <Link className="text-emerald-700" to={`/journal-entries/${x.journal_entry_id}`}>{x.journal_number}</Link></p>}
      </Card>
    </div>
  );
}
