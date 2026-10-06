import { ArrowLeft } from "lucide-react";
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import Input from "@/components/ui/Input";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { listLocations } from "@/modules/admin/organization/api";
import SearchableSelect from "@/components/form/SearchableSelect";
import useFormRecovery from "@/hooks/useFormRecovery";
import FormRecoveryActions from "@/components/form/FormRecoveryActions";
import { getJournal, journalAction, updateJournal } from "./api";
import { paymentAction } from "@/modules/finance/payments/api";
import { sourceDocumentPath } from "./sourceDocument";

type EditLine = {
  account_id: number;
  debit: number;
  credit: number;
  description: string;
  department_id?: number | null;
  location_id?: number | null;
};

const blankLine = (): EditLine => ({ account_id: 0, debit: 0, credit: 0, description: "" });

type JournalEditInput = { postingDate: string; locationId?: number; description: string; lines: EditLine[] };
const validEditInput = (v: unknown): v is JournalEditInput => { const x = v as JournalEditInput; return !!x && typeof x.postingDate === "string" && typeof x.description === "string" && Array.isArray(x.lines) && x.lines.every(l => typeof l.account_id === "number" && typeof l.debit === "number" && typeof l.credit === "number" && typeof l.description === "string"); };
export default function JournalDetailPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const qc = useQueryClient();
  const [editOpen, setEditOpen] = useState(false);
  const [postingDate, setPostingDate] = useState("");
  const [locationId, setLocationId] = useState<number>();
  const [description, setDescription] = useState("");
  const [lines, setLines] = useState<EditLine[]>([]);

  const recovery = useFormRecovery(`journal:edit:${id}`, { postingDate, locationId, description, lines }, editOpen, validEditInput);

  const q = useQuery({ queryKey: ["journal-entry", id], queryFn: () => getJournal(Number(id)), enabled: !!id });
  const accounts = useQuery({
    queryKey: ["journal-account-lookup"],
    queryFn: () => getAllAccountLookup({ is_posting: true, is_active: true }),
    enabled: editOpen,
  });

  const locations = useQuery({
    queryKey: ["journal-edit-locations", q.data?.business_unit_id],
    queryFn: () => listLocations({ business_unit_id: q.data?.business_unit_id ?? undefined, is_active: true }),
    enabled: editOpen,
  });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: ["journal-entry", id] });
    qc.invalidateQueries({ queryKey: ["journal-entries"] });
    qc.invalidateQueries({ queryKey: ["general-ledger"] });
    qc.invalidateQueries({ queryKey: ["trial-balance"] });
    qc.invalidateQueries({ queryKey: ["accounts-payable-aging"] });
    qc.invalidateQueries({ queryKey: ["finance-dashboard"] });
    qc.invalidateQueries({ queryKey: ["eligible-payment-invoices"] });
    qc.invalidateQueries({ queryKey: ["payment"] });
    qc.invalidateQueries({ queryKey: ["payments"] });
    qc.invalidateQueries({ queryKey: ["supplier-invoice"] });
    qc.invalidateQueries({ queryKey: ["supplier-invoices"] });
    qc.invalidateQueries({ queryKey: ["ap-reporting"] });
  };

  const act = useMutation({
    mutationFn: (action: string) => journalAction(Number(id), action),
    onSuccess: (_, action) => {
      toast.success(action === "unpost" ? "Journal returned to draft and the source document was synchronized." : `Journal ${action}ed.`);
      refresh();
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Journal action failed."),
  });

  const voidSourcePayment = useMutation({
    mutationFn: () => paymentAction(Number(q.data?.reference_id), "void"),
    onSuccess: () => {
      toast.success("Payment and its draft journal were voided.");
      refresh();
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Payment could not be voided."),
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
      location_id: locationId ?? null,
      description: description.trim() || null,
      lines: validLines.map((line) => ({
        account_id: line.account_id,
        debit: line.debit,
        credit: line.credit,
        description: line.description.trim() || undefined,
        department_id: line.department_id ?? null,
        location_id: locationId ?? null,
      })),
    }),
    onSuccess: () => {
      toast.success("Draft journal updated.");
      recovery.clear();
      setEditOpen(false);
      refresh();
    },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Journal could not be updated."),
  });

  if (q.isLoading) return <Loading/>;
  if (!q.data) return <p>Journal not found.</p>;
  const x = q.data;
  const a = x.allowed_actions;
  const sourcePath = sourceDocumentPath(x.reference_type, x.reference_id);

  const openEditor = () => {
    const saved = recovery.load();
    if (saved) { setPostingDate(saved.postingDate); setLocationId(saved.locationId); setDescription(saved.description); setLines(saved.lines); setEditOpen(true); recovery.notifyRestored(); return; }
    setPostingDate(x.journal_date);
    setLocationId(x.location_id ?? undefined);
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

  const confirmUnpost = () => {
    const source = (x.reference_type || "MANUAL").replaceAll("_", " ");
    if (!window.confirm(`Unpost ${x.journal_number}?\n\nThis will remove its General Ledger rows and synchronize the ${source} source document back to its editable/pre-posting state. Closed fiscal periods remain locked.`)) return;
    act.mutate("unpost");
  };

  return <div className="space-y-6">
    <div className="flex flex-wrap justify-between gap-3">
      <div className="flex items-center gap-3"><Button variant="outline" onClick={() => nav("/journal")}><ArrowLeft size={16}/> Back</Button><h1 className="text-2xl font-bold">{x.journal_number}</h1><Badge>{x.status}</Badge></div>
      <div className="flex flex-wrap gap-2">
        {sourcePath && <Button variant="outline" onClick={() => nav(sourcePath, { state: { returnTo: `/journal-entries/${x.id}` } })}>Open Source Document</Button>}
        <PrintPreviewButton src={`/journal-entries/${x.id}/print`} title={`Journal ${x.journal_number}`} ariaLabel="Preview journal" />
        {a.can_edit && <Button variant="outline" onClick={openEditor}>Edit</Button>}
        {a.can_post && <Button loading={act.isPending} onClick={() => act.mutate("post")}>Post</Button>}
        {a.can_unpost && <Button loading={act.isPending} variant="outline" onClick={confirmUnpost}>Unpost</Button>}
        {a.can_void && <Button variant="danger" loading={act.isPending} onClick={() => act.mutate("void")}>Void</Button>}
        {a.can_void_source_payment && <Button variant="danger" loading={voidSourcePayment.isPending} onClick={() => { if (window.confirm(`Void payment ${x.reference_number} and its draft journal ${x.journal_number}? This releases the invoice reservation and keeps both records as VOID.`)) voidSourcePayment.mutate(); }}>Void Payment & Journal</Button>}
      </div>
    </div>
    <Card><div className="grid gap-4 md:grid-cols-4"><div><small>Date</small><div>{x.journal_date}</div></div><div><small>Source</small><div>{(x.reference_type || "MANUAL").replaceAll("_", " ")}</div></div><div><small>Work Location</small><div>{x.location_name || (x.location_id ? `Location #${x.location_id}` : "Missing — edit before posting")}</div></div><div><small>Reference</small><div>{sourcePath?<Link className="font-medium text-emerald-700 hover:underline" to={sourcePath} state={{returnTo:`/journal-entries/${x.id}`}}>{x.reference_number||"View Source Document"}</Link>:x.reference_number||"—"}</div></div><div><small>Created By</small><div>{x.created_by_name || "—"}</div></div><div className="md:col-span-4"><small>Description</small><div>{x.description || "—"}</div></div></div></Card>
    <Card><Table variant="grid" className="min-w-[820px]" containerClassName="border-0 shadow-none"><THead><TR className="whitespace-nowrap"><TH>Account</TH><TH>Description</TH><TH numeric>Debit</TH><TH numeric>Credit</TH><TH>Organization</TH></TR></THead><TBody>{x.lines.map((l: any) => <TR key={l.id} className="whitespace-nowrap"><TD className="max-w-[280px]"><TableCellStack primary={l.account_name} secondary={l.account_code}/></TD><TD className="max-w-[280px]"><span className="block truncate" title={l.description || undefined}>{l.description || "—"}</span></TD><TD numeric className="w-40">{Number(l.debit).toLocaleString("id-ID",{minimumFractionDigits:2,maximumFractionDigits:2})}</TD><TD numeric className="w-40">{Number(l.credit).toLocaleString("id-ID",{minimumFractionDigits:2,maximumFractionDigits:2})}</TD><TD>{l.department_name || l.location_name ? <TableCellStack primary={l.department_name || l.location_name} secondary={l.department_name ? l.location_name : undefined}/> : "—"}</TD></TR>)}</TBody></Table></Card>
    <Card><div className="grid grid-cols-3 gap-4 text-right"><div><small>Total Debit</small><div className="text-lg font-bold tabular-nums">{Number(x.total_debit).toLocaleString(undefined,{minimumFractionDigits:2})}</div></div><div><small>Total Credit</small><div className="text-lg font-bold tabular-nums">{Number(x.total_credit).toLocaleString(undefined,{minimumFractionDigits:2})}</div></div><div><small>Difference</small><div className="text-lg font-bold tabular-nums">{Number(x.difference).toLocaleString(undefined,{minimumFractionDigits:2})}</div></div></div></Card>
    {x.status === "POSTED" && !a.can_unpost && <p className="text-xs text-slate-500">This journal cannot be safely unposted from Journal. Reverse it from the originating module or reopen the required fiscal period first.</p>}

    <Dialog open={editOpen} onOpenChange={next => { if (!save.isPending) setEditOpen(next); }}>
      <DialogContent className="max-w-5xl">
        <DialogHeader><DialogTitle>Edit Draft Journal {x.journal_number}</DialogTitle></DialogHeader>
        <DialogBody className="space-y-5">
          <div className="grid gap-4 md:grid-cols-3">
            <label className="text-sm font-medium">Posting Date<Input className="mt-1" type="date" value={postingDate} onChange={(e) => setPostingDate(e.target.value)} /></label>
            <label className="text-sm font-medium">Description<Input className="mt-1" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
            <SearchableSelect label="Work Location" required value={locationId} disabled={locations.isLoading} placeholder="Select work location..." options={(locations.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}))} onChange={setLocationId} />
          </div>
          <div className="overflow-x-auto rounded-lg border">
            <table className="min-w-[850px] w-full text-sm">
              <thead className="bg-slate-50"><tr><th className="p-3 text-left">Account</th><th className="p-3 text-left">Description</th><th className="w-44 p-3 text-right">Debit</th><th className="w-44 p-3 text-right">Credit</th><th /></tr></thead>
              <tbody>{lines.map((line, index) => <tr key={index} className="border-t">
                <td className="p-2"><SearchableSelect value={line.account_id || undefined} disabled={accounts.isLoading || accounts.isError} placeholder={accounts.isLoading ? "Loading accounts..." : accounts.isError ? "Could not load accounts" : "Type account code or name..."} options={(accounts.data ?? []).filter(account=>!["REVENUE","INCOME"].includes(account.account_type)||account.account_code==="400"||account.id===line.account_id).map((account) => ({ id: account.id, label: `${account.account_code} — ${account.account_name}`, keywords: [account.account_code, account.account_name, account.account_type, account.account_subtype] }))} maxOptions={1000} onChange={(value) => updateLine(index, { account_id: value ?? 0 })} /></td>
                <td className="p-2"><Input value={line.description} onChange={(e) => updateLine(index, { description: e.target.value })} /></td>
                <td className="w-44 p-2"><CurrencyInput value={line.debit} onValueChange={(value) => updateLine(index, { debit: value, credit: value > 0 ? 0 : line.credit })} /></td>
                <td className="w-44 p-2"><CurrencyInput value={line.credit} onValueChange={(value) => updateLine(index, { credit: value, debit: value > 0 ? 0 : line.debit })} /></td>
                <td className="p-2"><Button type="button" size="xs" variant="danger" disabled={lines.length <= 2} onClick={() => setLines(lines.filter((_, i) => i !== index))}>Remove</Button></td>
              </tr>)}</tbody>
            </table>
          </div>
          <div className="flex items-center justify-between gap-4">
            <Button type="button" variant="outline" onClick={() => setLines([...lines, blankLine()])}>Add Line</Button>
            <div className={`rounded-lg border px-5 py-3 text-sm ${balanced ? "bg-emerald-50" : "bg-amber-50"}`}>
              <div>Debit: <strong className="tabular-nums">{totals.debit.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div>
              <div>Credit: <strong className="tabular-nums">{totals.credit.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div>
              <div>Difference: <strong className="tabular-nums">{Math.abs(totals.debit - totals.credit).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div>
            </div>
          </div>
        </DialogBody>
        <DialogFooter><FormRecoveryActions failed={recovery.failed} disabled={save.isPending} onDiscard={() => { recovery.clear(); setEditOpen(false); }} /><Button variant="outline" disabled={save.isPending} onClick={() => setEditOpen(false)}>Close</Button><Button loading={save.isPending} disabled={!postingDate || !locationId || validLines.length < 2 || !balanced} onClick={() => save.mutate()}>Save Changes</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  </div>;
}
