import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Printer } from "lucide-react";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Loading from "@/components/ui/Loading";
import { getTransfer, transferAction, updateTransfer } from "./api";
export default function BankTransferDetailPage() {
  const { id } = useParams(),
    nav = useNavigate(),
    qc = useQueryClient(),
    q = useQuery({
      queryKey: ["bank-transfer", id],
      queryFn: () => getTransfer(Number(id)),
      enabled: !!id,
    }),
    act = useMutation({
      mutationFn: () => transferAction(Number(id), "post"),
      onSuccess: () => {
        toast.success("Transfer posted");
        qc.invalidateQueries({ queryKey: ["bank-transfer", id] });
      },
      onError: (e: any) =>
        toast.error(e.response?.data?.detail || "Posting failed"),
    }),
    edit = useMutation({
      mutationFn: (payload: any) => updateTransfer(Number(id), payload),
      onSuccess: () => {
        toast.success("Transfer updated");
        qc.invalidateQueries({ queryKey: ["bank-transfer", id] });
      },
      onError: (e: any) =>
        toast.error(e.response?.data?.detail || "Update failed"),
    });
  if (q.isLoading) return <Loading />;
  const x = q.data;
  if (!x) return <p>Transfer not found.</p>;
  return (
    <div className="space-y-6">
      <div className="flex justify-between">
        <div className="flex items-center gap-3">
          <Button variant="outline" onClick={() => nav("/bank-transfers")}>
            <ArrowLeft size={16} /> Back
          </Button>
          <h1 className="text-2xl font-bold">{x.transfer_number}</h1>
          <Badge>{x.status}</Badge>
        </div>
        <div className="flex gap-2">
          <Button
            variant="outline"
            onClick={() =>
              window.open(`/bank-transfers/${x.id}/print`, "_blank")
            }
          >
            <Printer size={17} />
          </Button>
          {x.allowed_actions.can_edit && (
            <Button variant="outline" onClick={() => {
              const amount = window.prompt("Transfer amount", String(x.amount));
              if (amount === null) return;
              const reference_number = window.prompt("Reference number", x.reference_number || "");
              if (reference_number === null) return;
              const notes = window.prompt("Notes", x.notes || "");
              if (notes === null) return;
              edit.mutate({ transfer_date: x.transfer_date, source_account_id: x.source_account_id, destination_account_id: x.destination_account_id, amount: Number(amount), currency: x.currency, reference_number, notes });
            }}>
              Edit
            </Button>
          )}
          {x.allowed_actions.can_post && (
            <Button onClick={() => act.mutate()}>Post</Button>
          )}
        </div>
      </div>
      <Card>
        <div className="grid gap-4 md:grid-cols-4">
          <div>
            <small>Date</small>
            <div>{x.transfer_date}</div>
          </div>
          <div>
            <small>Source</small>
            <div>
              {x.source_account_code} — {x.source_account_name}
            </div>
          </div>
          <div>
            <small>Destination</small>
            <div>
              {x.destination_account_code} — {x.destination_account_name}
            </div>
          </div>
          <div>
            <small>Amount</small>
            <div>
              {Number(x.amount).toLocaleString()} {x.currency}
            </div>
          </div>
          <div>
            <small>Reference</small>
            <div>{x.reference_number || "—"}</div>
          </div>
          <div>
            <small>Notes</small>
            <div>{x.notes || "—"}</div>
          </div>
        </div>
        {x.journal_entry_id && (
          <p className="mt-4">
            Related Journal:{" "}
            <Link
              className="text-emerald-700"
              to={`/journal-entries/${x.journal_entry_id}`}
            >
              {x.journal_number}
            </Link>
          </p>
        )}
      </Card>
    </div>
  );
}
