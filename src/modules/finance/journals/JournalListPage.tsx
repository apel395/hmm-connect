import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import { filterBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { isBeforeToday, todayLocal } from "@/utils/dateConstraints";
import { createJournal, journalAction, listJournals } from "./api";

type Line = { account_id: number; debit: number; credit: number; description: string };
const blankLine = (): Line => ({ account_id: 0, debit: 0, credit: 0, description: "" });

export default function JournalListPage() {
  const nav = useNavigate();
  const client = useQueryClient();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [open, setOpen] = useState(false);
  const [postingDate, setPostingDate] = useState(todayLocal());
  const [documentNumber, setDocumentNumber] = useState("");
  const [description, setDescription] = useState("Salary journal");
  const [businessUnitId, setBusinessUnitId] = useState<number>();
  const [departmentId, setDepartmentId] = useState<number>();
  const [locationId, setLocationId] = useState<number>();
  const [lines, setLines] = useState<Line[]>([blankLine(), blankLine()]);

  const q = useQuery({ queryKey: ["journal-entries", page, search, status], queryFn: () => listJournals({ page, page_size: 20, search: search || undefined, status: status || undefined }) });
  const accounts = useQuery({ queryKey: ["journal-account-lookup"], queryFn: () => getAccountLookup({ is_posting: true, is_active: true }), enabled: open });
  const businessUnits = useQuery({ queryKey: ["business-units", "manual-journal", "active"], queryFn: () => filterBusinessUnits({ is_active: true }), enabled: open });
  const departments = useQuery({ queryKey: ["journal-departments", businessUnitId], queryFn: () => listDepartments({ business_unit_id: businessUnitId, is_active: true }), enabled: open && Boolean(businessUnitId) });
  const locations = useQuery({ queryKey: ["journal-locations", businessUnitId], queryFn: () => listLocations({ business_unit_id: businessUnitId, is_active: true }), enabled: open && Boolean(businessUnitId) });

  useEffect(() => {
    if (open && !businessUnitId && businessUnits.data?.length === 1) setBusinessUnitId(businessUnits.data[0].id);
  }, [open, businessUnitId, businessUnits.data]);

  const totals = useMemo(() => lines.reduce((sum, line) => ({ debit: sum.debit + line.debit, credit: sum.credit + line.credit }), { debit: 0, credit: 0 }), [lines]);
  const validLines = lines.filter((line) => line.account_id > 0 && (line.debit > 0 || line.credit > 0));

  const refreshFinance = () => {
    client.invalidateQueries({ queryKey: ["journal-entries"] });
    client.invalidateQueries({ queryKey: ["general-ledger"] });
    client.invalidateQueries({ queryKey: ["trial-balance"] });
    client.invalidateQueries({ queryKey: ["accounts-payable-aging"] });
  };

  const lifecycle = useMutation({
    mutationFn: ({ id, action }: { id: number; action: "post" | "unpost" }) => journalAction(id, action),
    onSuccess: (_, vars) => { toast.success(vars.action === "post" ? "Journal posted." : "Journal returned to draft."); refreshFinance(); },
    onError: (error: any) => toast.error(error?.response?.data?.detail || "Journal action failed."),
  });

  const save = useMutation({
    mutationFn: () => createJournal({
      posting_date: postingDate, document_type: "MANUAL_JOURNAL", document_number: documentNumber.trim(), reference_type: "MANUAL", reference_id: 0,
      description: description.trim() || undefined, business_unit_id: businessUnitId!, department_id: departmentId ?? null, location_id: locationId ?? null,
      lines: validLines.map((line) => ({ ...line, description: line.description || undefined, business_unit_id: businessUnitId, department_id: departmentId ?? null, location_id: locationId ?? null })),
    }),
    onSuccess: (journal) => { toast.success("Journal entry created."); setOpen(false); setPostingDate(todayLocal()); setDocumentNumber(""); setDescription("Salary journal"); setDepartmentId(undefined); setLocationId(undefined); setBusinessUnitId(businessUnits.data?.length === 1 ? businessUnits.data[0].id : undefined); setLines([blankLine(), blankLine()]); refreshFinance(); nav(`/journal-entries/${journal.id}`); },
    onError: (error: any) => toast.error(typeof error?.response?.data?.detail === "string" ? error.response.data.detail : "Journal entry could not be created."),
  });

  const updateLine = (index: number, patch: Partial<Line>) => setLines(lines.map((line, i) => i === index ? { ...line, ...patch } : line));
  const balanced = totals.debit > 0 && Math.abs(totals.debit - totals.credit) < 0.005;
  const valid = Boolean(documentNumber.trim() && businessUnitId && validLines.length >= 2 && balanced && postingDate && !isBeforeToday(postingDate));
  const selectClass = "mt-1 h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm";
  const changeBusinessUnit = (value?: number) => { setBusinessUnitId(value); setDepartmentId(undefined); setLocationId(undefined); };
  const createJournalEntry = () => { if (isBeforeToday(postingDate)) return toast.error("Posting Date cannot be before today."); save.mutate(); };

  return <>
    <PageHeader title="Journal Entries" description="Review debit and credit entries, then post or safely unpost eligible journals." actions={<Button onClick={() => { setPostingDate(todayLocal()); setOpen(true); }}>Create Journal Entry</Button>} />
    <Card><div className="mb-4 flex gap-3"><input className="h-10 flex-1 rounded border px-3" placeholder="Search journal, document, or description" value={search} onChange={(e) => setSearch(e.target.value)} /><select className="h-10 rounded border px-3" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All statuses</option><option>DRAFT</option><option>POSTED</option><option>VOID</option></select></div>
      <Table className="min-w-[850px]" containerClassName="border-0 shadow-none">
        <THead><TR className="whitespace-nowrap"><TH>Journal</TH><TH>Date</TH><TH>Document</TH><TH>Description</TH><TH numeric>Amount</TH><TH>Status</TH><TH numeric>Actions</TH></TR></THead>
        <TBody>{q.data?.items.map((x: any) => <TR key={x.id} className="whitespace-nowrap">
          <TD><TableCellStack primary={x.journal_number} secondary={x.reference_type?.replaceAll("_", " ")}/></TD>
          <TD>{x.journal_date}</TD>
          <TD className="font-medium">{x.reference_number || "—"}</TD>
          <TD className="max-w-[280px]"><span className="block truncate" title={x.description || undefined}>{x.description || "—"}</span></TD>
          <TD numeric className="font-semibold">{Number(x.total_debit).toLocaleString("id-ID", { minimumFractionDigits: 2 })}</TD>
          <TD>{x.status}</TD>
          <TD><div className="flex justify-end gap-2"><Button size="xs" variant="outline" onClick={() => nav(`/journal-entries/${x.id}`)}>View</Button>{x.allowed_actions?.can_post&&<Button size="xs" loading={lifecycle.isPending} onClick={()=>lifecycle.mutate({id:x.id,action:"post"})}>Post</Button>}{x.allowed_actions?.can_unpost&&<Button size="xs" variant="outline" loading={lifecycle.isPending} onClick={()=>lifecycle.mutate({id:x.id,action:"unpost"})}>Unpost</Button>}</div></TD>
        </TR>)}</TBody>
      </Table>
      <div className="mt-4 flex justify-end gap-2"><Button variant="outline" disabled={!q.data?.has_previous} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" disabled={!q.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button></div></Card>

    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-5xl"><DialogHeader><DialogTitle>Create Journal Entry</DialogTitle></DialogHeader><DialogBody className="space-y-5">
      <div className="grid gap-4 md:grid-cols-3">
        <label className="text-sm font-medium">Posting Date<Input className="mt-1" type="date" min={todayLocal()} value={postingDate} onChange={(e) => setPostingDate(e.target.value)} /></label>
        <label className="text-sm font-medium">Document Number<Input className="mt-1" placeholder="PAYROLL-2026-08" value={documentNumber} onChange={(e) => setDocumentNumber(e.target.value)} /></label>
        <label className="text-sm font-medium">Description<Input className="mt-1" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <label className="text-sm font-medium">Business Unit *<select required className={selectClass} value={businessUnitId ?? ""} onChange={(e) => changeBusinessUnit(e.target.value ? Number(e.target.value) : undefined)}><option value="">Select business unit</option>{(businessUnits.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.code} — {item.name}</option>)}</select></label>
        <label className="text-sm font-medium">Department<select disabled={!businessUnitId} className={selectClass} value={departmentId ?? ""} onChange={(e) => setDepartmentId(e.target.value ? Number(e.target.value) : undefined)}><option value="">Optional</option>{(departments.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.code} — {item.name}</option>)}</select></label>
        <label className="text-sm font-medium">Location<select disabled={!businessUnitId} className={selectClass} value={locationId ?? ""} onChange={(e) => setLocationId(e.target.value ? Number(e.target.value) : undefined)}><option value="">Optional</option>{(locations.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.code} — {item.name}</option>)}</select></label>
      </div>
      <div className="rounded border border-slate-200 bg-slate-50 p-3 text-sm text-slate-600">The selected organization context is applied to every line in this manual journal, including salary journals.</div>
      <div className="overflow-x-auto rounded-lg border"><table className="min-w-[850px] w-full text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-left">Account</th><th className="p-3 text-left">Line Description</th><th className="p-3 text-right">Debit</th><th className="p-3 text-right">Credit</th><th /></tr></thead><tbody>{lines.map((line, index) => <tr key={index} className="border-t"><td className="p-2"><select className="h-10 w-full rounded border px-2" value={line.account_id || ""} onChange={(e) => updateLine(index, { account_id: Number(e.target.value) })}><option value="">Select posting account</option>{accounts.data?.map((account) => <option key={account.id} value={account.id}>{account.account_code} - {account.account_name}</option>)}</select></td><td className="p-2"><Input value={line.description} onChange={(e) => updateLine(index, { description: e.target.value })} /></td><td className="p-2"><CurrencyInput value={line.debit} onValueChange={(value) => updateLine(index, { debit: value, credit: value > 0 ? 0 : line.credit })} /></td><td className="p-2"><CurrencyInput value={line.credit} onValueChange={(value) => updateLine(index, { credit: value, debit: value > 0 ? 0 : line.debit })} /></td><td className="p-2"><Button type="button" size="xs" variant="danger" disabled={lines.length <= 2} onClick={() => setLines(lines.filter((_, i) => i !== index))}>Remove</Button></td></tr>)}</tbody></table></div>
      <div className="flex items-center justify-between"><Button type="button" variant="outline" onClick={() => setLines([...lines, blankLine()])}>Add Line</Button><div className={`rounded-lg border px-5 py-3 text-sm ${balanced ? "bg-emerald-50" : "bg-amber-50"}`}><div>Debit: <strong>{totals.debit.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div><div>Credit: <strong>{totals.credit.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div><div>Difference: <strong>{Math.abs(totals.debit - totals.credit).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></div></div></div>
    </DialogBody><DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button loading={save.isPending} disabled={!valid} onClick={createJournalEntry}>Create Draft Journal</Button></DialogFooter></DialogContent></Dialog>
  </>;
}
