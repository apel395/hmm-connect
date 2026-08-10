import { ArrowLeft } from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Loading from "@/components/ui/Loading";
import Input from "@/components/ui/Input";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import { AdminJournalUnpostButton } from "@/modules/admin-overrides/AdminOverrideActions";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { getJournal, journalAction, updateJournal } from "./api";

type EditLine = {
  account_id: number;
  debit: number;
  credit: number;
  description: string;
  department_id?: number | null;
  location_id?: number | null;
};

const blankLine = (): EditLine => ({ account_id: 0, debit: 0, credit: 0, description: "" });

export default function JournalDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [postingDate, setPostingDate] = useState("");
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState<EditLine[]>([]);

  const q = useQuery({ queryKey: ["journal-entry", id], queryFn: () => getJournal(Number(id)), enabled: !!id });
  const accounts = useQuery({
    queryKey: ["journal-account-lookup"],
    queryFn: () => getAccountLookup({ is_posting: true, is_active: true }),
    enabled: editOpen,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["journal-entry", id] });
    qc.invalidateQueries({ queryKey: ["journal-entries"] });
    qc.invalidateQueries({ queryKey: ["general-ledger"] });
    qc.invalidateQueries({ queryKey: ["trial-balance"] });
    qc.invalidateQueries({ queryKey: ["accounts-payable-aging"] });
    qc.invalidateQueries({ queryKey: ["supplier-invoices"] });
    qc.invalidateQueries({ queryKey: ["payments"] });
    qc.invalidateQueries({ queryKey: ["cash-accounts"] });
    qc.invalidateQueries({ queryKey: ["finance-dashboard"] });
  };

  const act = useMutation({
    mutationFn: (action: string) => journalAction(Number(id), action),
    onSuccess: (_, action) => {
      toast.success(action === "unpost" ? "Journal returned to draft." : `Journal ${action}ed.`);
      refresh();
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Journal action failed."),
  });

  const totals = useMemo(
    () => lines.reduce((sum, line) => ({ debit: sum.debit + line.debit, credit: sum.credit + line.credit }), { debit: 0, credit: 0 }),
    [lines],
  );
  const validLines = lines.filter((line) => line.account_id > 0 && (line.debit > 0 || line.credit > 0));
  const balanced = totals.debit > 0 && Math.abs(totals.debit - totals.credit) < 0.005;

  const save = useMutation({
    mutationFn: () => updateJournal(Number(id), {
      posting_date: postingDate,
      description: description.trim() || null,
      lines: validLines.map((line) => ({
        account_id: line.account_id,
        debit: line.debit,
        credit: line.credit,
        description: line.description.trim() || undefined,
        department_id: line.department_id ?? null,
        location_id: line.location_id ?? null,
      })),
    }),
    onSuccess: () => {
      toast.success("Draft journal updated.");
      setEditOpen(false);
      refresh();
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Journal could not be updated."),
  });

  if (q.isLoading) return <Loading/>;
  if (!q.data) return <p>Journal not found.</p>;
  const x = q.data;
  const a = x.allowed_actions;

  const openEditor = () => {
    setPostingDate(x.journal_date);
    setDescription(x.description || "");
    setLines(x.lines.map((line) => ({
      account_id: line.account_id,
      debit: Number(line.debit || 0),
      credit: Number(line.credit || 0),
      description: line.description || "",
      department_id: line.department_id ?? null,
      location_id: line.location_id ?? null,
    })));
    setEditOpen(true);
  };

  const updateLine = (index: number, patch: Partial<EditLine>) => {
    setLines((current) => current.map((line, i) => i === index ? { ...line, ...patch } : line));
  };

  return <div className="space-y-6">
    <div className="flex flex-wrap justify-between gap-3">
      <div className="flex items-center gap-3"><Button variant="outline" onClick={() => nav("/journal")}><ArrowLeft size={16}/> Back</Button><h1 className="text-2xl font-bold">{x.journal_number}</h1><Badge>{x.status}</Badge></div>
      <div className="flex flex-wrap gap-2">
        <PrintPreviewButton src={`/journal-entries/${x.id}/print`} title={`Journal ${x.journal_number}`} ariaLabel="Preview journal" />
        {a.can_edit && <Button variant="outline" onClick={openEditor}>Edit</Button>}
        {a.can_post && <Button loading={act.isPending} onClick={() => act.mutate("post")}>Post</Button>}
        {a.can_unpost && <Button loading={act.isPending} variant="outline" onClick={() => act.mutate("unpost")}>Unpost</Button>}
        {!a.can_unpost && <AdminJournalUnpostButton journalId={x.id} status={x.status} onSuccess={refresh}/>} 
        {a.can_void && <Button variant="danger" loading={act.isPending} onClick={() => act.mutate("void")}>Void</Button>}
      </div>
    </div>
    <Card><div className="grid gap-4 md:grid-cols-4"><div><small>Date</small><div>{x.journal_date}</div></div><div><small>Reference</small><div>{x.reference_number || "—"}</div></div><div><small>Description</small><div>{x.description || "—"}</div></div><div><small>Created By</small><div>{x.created_by_name || "—"}</div></div></div></Card>
    <Card className="overflow-x-auto"><table className="table-grid w-full text-sm"><thead><tr className="border-b text-left"><th className="p-3">Account Code</th><th>Account Name</th><th>Description</th><th className="text-right">Debit</th><th className="text-right">Credit</th><th>Department</th><th>Location</th></tr></thead><tbody>{x.lines.map((l: any) => <tr key={l.id} className="border-b"><td className="p-3">{l.account_code}</td><td>{l.account_name}</td><td>{l.description || "—"}</td><td className="text-right">{Number(l.debit).toLocaleString()}</td><td className="text-right">{Number(l.credit).toLocaleString()}</td><td>{l.department_name || "—"}</td><td>{l.location_name || "—"}</td></tr>)}</tbody></table></Card>
    <Card><div className="grid grid-cols-3 gap-4 text-right"><div><small>Total Debit</small><div className="text-lg font-bold">{Number(x.total_debit).toLocaleString()}</div></div><div><small>Total Credit</small><div className="text-lg font-bold">{Number(x.total_credit).toLocaleString()}</div></div><div><small>Difference</small><div className="text-lg font-bold">{Number(x.difference).toLocaleString()}</div></div></div></Card>
    {x.status === "POSTED" && !a.can_unpost && <p className="text-xs text-slate-500">Normal users must reverse this source journal from its originating document. Administrators may use Admin Unpost; the backend synchronizes the source document and GL in one transaction.</p>}

    <Dialog open={editOpen} onOpenChange={setEditOpen}>
      <DialogContent className="max-w-5xl">
        <DialogHeader><DialogTitle>Edit Draft Journal {x.journal_number}</DialogTitle></DialogHeader>
        <DialogBody className="space-y-5">
          <div className="grid gap-4 md:grid-cols-2">
            <label className="text-sm font-medium">Posting Date<Input className="mt-1" type="date" value={postingDate} onChange={(e) => setPostingDate(e.target.value)} /></label>
            <label className="text-sm font-medium">Description<Input className="mt-1" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
          </div>
          <div className="overflow-x-auto rounded-lg border">
            <table className="table-fixed min-w-[900px] w-full text-sm">
              <thead className="bg-slate-50"><tr><th className="w-72 p-3 text-left">Account</th><th className="w-64 p-3 text-left">Description</th><th className="w-40 p-3 text-right">Debit</th><th className="w-40 p-3 text-right">Credit</th><th className="w-24" /></tr></thead>
              <tbody>{lines.map((line, index) => <tr key={index} className="border-t">
                <td className="p-2"><select className="h-10 w-full rounded border px-2" value={line.account_id || ""} onChange={(e) => updateLine(index, { account_id: Number(e.target.value) })}><option value="">Select posting account</option>{accounts.data?.map((account) => <option key={account.id} value={account.id}>{account.account_code} - {account.account_name}</option>)}</select></td>
                <td className="p-2"><Input value={line.description} onChange={(e) => updateLine(index, { description: e.target.value })} /></td>
                <td className="p-2"><div className="min-w-36"><CurrencyInput value={line.debit} onValueChange={(value) => updateLine(index, { debit: value, credit: value > 0 ? 0 : line.credit })} /></div></td>
                <td className="p-2"><div className="min-w-36"><CurrencyInput value={line.credit} onValueChange={(value) => updateLine(index, { credit: value, debit: value > 0 ? 0 : line.debit })} /></div></td>
                <td className="p-2"><Button type="button" size="xs" variant="danger" disabled={lines.length <= 2} onClick={() => setLines(lines.filter((_, i) => i !== index))}>Remove</Button></td>
              </tr>)}</tbody>
            </table>
          </div>
          <div className="flex items-center justify-between gap-4">
            <Button type="button" variant="outline" onClick={() => setLines([...lines, blankLine()])}>Add Line</Button>
            <div className={`rounded-lg border px-5 py-3 text-sm ${balanced ? "bg-emerald-50" : "bg-amber-50"}`}>
              <div>Debit: <strong>{totals.debit.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div>
              <div>Credit: <strong>{totals.credit.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div>
              <div>Difference: <strong>{Math.abs(totals.debit - totals.credit).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div>
            </div>
          </div>
        </DialogBody>
        <DialogFooter><Button variant="outline" onClick={() => setEditOpen(false)}>Cancel</Button><Button loading={save.isPending} disabled={!postingDate || validLines.length < 2 || !balanced} onClick={() => save.mutate()}>Save Changes</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </div>;
}
