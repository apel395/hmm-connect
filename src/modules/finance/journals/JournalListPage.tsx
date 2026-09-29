import { useCallback, useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Input from "@/components/ui/Input";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import SearchableSelect from "@/components/form/SearchableSelect";
import JournalBulkImportDialog from "./JournalBulkImportDialog";
import { filterBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { supplierApi } from "@/modules/master/suppliers/api/supplierApi";
import { isBeforeToday, todayLocal } from "@/utils/dateConstraints";
import { bulkJournalAction, createJournal, journalAction, listJournals } from "./api";
import { sourceDocumentPath } from "./sourceDocument";
import { paymentAction } from "@/modules/finance/payments/api";
import useAuthorization from "@/hooks/useAuthorization";

type Line = { account_id: number; debit: number; credit: number; description: string };
const blankLine = (): Line => ({ account_id: 0, debit: 0, credit: 0, description: "" });

export default function JournalListPage() {
  const nav = useNavigate();
  const client = useQueryClient();
  const { isSuperuser } = useAuthorization();
  const canBulkManage = isSuperuser();
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [filterLocationId, setFilterLocationId] = useState<number>();
  const [filterSupplierId, setFilterSupplierId] = useState<number>();
  const [open, setOpen] = useState(false);
  const [bulkImportOpen, setBulkImportOpen] = useState(false);
  const [postingDate, setPostingDate] = useState(todayLocal());
  const [documentNumber, setDocumentNumber] = useState("");
  const [description, setDescription] = useState("Salary journal");
  const [businessUnitId, setBusinessUnitId] = useState<number>();
  const [departmentId, setDepartmentId] = useState<number>();
  const [locationId, setLocationId] = useState<number>();
  const [lines, setLines] = useState<Line[]>([blankLine(), blankLine()]);
  const [selected, setSelected] = useState<number[]>([]);

  const q = useQuery({ queryKey: ["journal-entries", page, search, status, filterLocationId, filterSupplierId], queryFn: () => listJournals({ page, page_size: 20, search: search || undefined, status: status || undefined, location_id: filterLocationId ?? undefined, supplier_id: filterSupplierId ?? undefined }) });
  const accounts = useQuery({ queryKey: ["journal-account-lookup"], queryFn: () => getAllAccountLookup({ is_posting: true, is_active: true }), enabled: open });
  const businessUnits = useQuery({ queryKey: ["business-units", "manual-journal", "active"], queryFn: () => filterBusinessUnits({ is_active: true }), enabled: open });
  const departments = useQuery({ queryKey: ["journal-departments", businessUnitId], queryFn: () => listDepartments({ business_unit_id: businessUnitId, is_active: true }), enabled: open && Boolean(businessUnitId) });
  const locations = useQuery({ queryKey: ["journal-locations", businessUnitId], queryFn: () => listLocations({ business_unit_id: businessUnitId, is_active: true }), enabled: open && Boolean(businessUnitId) });
  const filterLocations = useQuery({ queryKey: ["journal-filter-locations", "active"], queryFn: () => listLocations({ is_active: true }) });
  const filterSuppliers = useQuery({ queryKey: ["journal-filter-suppliers"], queryFn: () => supplierApi.lookup("", 100) });

  useEffect(() => { setSelected([]); }, [page, search, status, filterLocationId, filterSupplierId]);
  useEffect(() => { if (open && !businessUnitId && businessUnits.data?.length === 1) setBusinessUnitId(businessUnits.data[0].id); }, [open, businessUnitId, businessUnits.data]);

  const totals = useMemo(() => lines.reduce((sum, line) => ({ debit: sum.debit + line.debit, credit: sum.credit + line.credit }), { debit: 0, credit: 0 }), [lines]);
  const validLines = lines.filter((line) => line.account_id > 0 && (line.debit > 0 || line.credit > 0));
  const refreshFinance = useCallback(() => { client.invalidateQueries({ queryKey: ["journal-entries"] }); client.invalidateQueries({ queryKey: ["journal-entry"] }); client.invalidateQueries({ queryKey: ["general-ledger"] }); client.invalidateQueries({ queryKey: ["trial-balance"] }); client.invalidateQueries({ queryKey: ["accounts-payable-aging"] }); client.invalidateQueries({ queryKey: ["ap-reporting"] }); client.invalidateQueries({ queryKey: ["supplier-invoices"] }); client.invalidateQueries({ queryKey: ["supplier-invoice"] }); client.invalidateQueries({ queryKey: ["eligible-payment-invoices"] }); client.invalidateQueries({ queryKey: ["eligible-payment-suppliers"] }); client.invalidateQueries({ queryKey: ["payments"] }); client.invalidateQueries({ queryKey: ["payment"] }); client.invalidateQueries({ queryKey: ["finance-dashboard"] }); client.invalidateQueries({ queryKey: ["balance-sheet"] }); client.invalidateQueries({ queryKey: ["profit-loss"] }); }, [client]);
  const voidSourcePayment = useMutation({ mutationFn: (paymentId: number) => paymentAction(paymentId, "void"), onSuccess: () => { toast.success("Payment and its draft journal were voided."); refreshFinance(); }, onError: (error: any) => toast.error(error?.response?.data?.detail || "Payment could not be voided.") });
  const lifecycle = useMutation({ mutationFn: ({ id, action }: { id: number; action: "post" | "unpost" }) => journalAction(id, action), onSuccess: (_, vars) => { toast.success(vars.action === "post" ? "Journal posted." : "Journal returned to draft."); refreshFinance(); }, onError: (error: any) => toast.error(error?.response?.data?.detail || "Journal action failed.") });
  const bulkLifecycle = useMutation({ mutationFn: ({ ids, action }: { ids: number[]; action: "post" | "unpost" }) => bulkJournalAction(ids, action), onSuccess: (result) => { toast.success(`${result.processed} journal(s) changed to ${result.status}.`); setSelected([]); refreshFinance(); }, onError: (error: any) => toast.error(error?.response?.data?.detail || "Bulk journal action failed. No journals were changed.") });
  const save = useMutation({ mutationFn: () => createJournal({ posting_date: postingDate, document_type: "MANUAL_JOURNAL", document_number: documentNumber.trim(), reference_type: "MANUAL", reference_id: 0, description: description.trim() || undefined, business_unit_id: businessUnitId!, department_id: departmentId ?? null, location_id: locationId ?? null, lines: validLines.map((line) => ({ ...line, description: line.description || undefined, business_unit_id: businessUnitId, department_id: departmentId ?? null, location_id: locationId ?? null })) }), onSuccess: (journal) => { toast.success("Journal entry created."); setOpen(false); setPostingDate(todayLocal()); setDocumentNumber(""); setDescription("Salary journal"); setDepartmentId(undefined); setLocationId(undefined); setBusinessUnitId(businessUnits.data?.length === 1 ? businessUnits.data[0].id : undefined); setLines([blankLine(), blankLine()]); refreshFinance(); nav(`/journal-entries/${journal.id}`); }, onError: (error: any) => toast.error(typeof error?.response?.data?.detail === "string" ? error.response.data.detail : "Journal entry could not be created.") });
  const updateLine = (index: number, patch: Partial<Line>) => setLines(lines.map((line, i) => i === index ? { ...line, ...patch } : line));
  const balanced = totals.debit > 0 && Math.abs(totals.debit - totals.credit) < 0.005;
  const valid = Boolean(documentNumber.trim() && businessUnitId && locationId && validLines.length >= 2 && balanced && postingDate && !isBeforeToday(postingDate));
  const changeBusinessUnit = (value?: number) => { setBusinessUnitId(value); setDepartmentId(undefined); setLocationId(undefined); };
  const createJournalEntry = () => { if (!locationId) return toast.error("Select a work location."); if (isBeforeToday(postingDate)) return toast.error("Posting Date cannot be before today."); save.mutate(); };
  const visibleRows: any[] = useMemo(() => q.data?.items ?? [], [q.data?.items]);
  const visibleTotals = useMemo(() => visibleRows.reduce((sum, row) => ({ debit: sum.debit + Number(row.total_debit || 0), credit: sum.credit + Number(row.total_credit || 0) }), { debit: 0, credit: 0 }), [visibleRows]);
  const filteredJournalTotals = q.data?.summary?.total_debit != null && q.data?.summary?.total_credit != null
    ? { debit: Number(q.data.summary.total_debit), credit: Number(q.data.summary.total_credit) }
    : null;
  const printQuery = new URLSearchParams(Object.fromEntries(Object.entries({ search, status, location_id: filterLocationId ? String(filterLocationId) : "", supplier_id: filterSupplierId ? String(filterSupplierId) : "" }).filter(([, value]) => value !== ""))).toString();
  const printSrc = `/journal/register/print${printQuery ? `?${printQuery}` : ""}`;
  const selectedRows = visibleRows.filter((row) => selected.includes(row.id));
  const bulkCandidates = (action: "post" | "unpost") => { const desiredStatus = action === "post" ? "DRAFT" : "POSTED"; const source = selectedRows.length ? selectedRows : visibleRows; return source.filter((row) => row.status === desiredStatus).map((row) => row.id); };
  const runBulk = (action: "post" | "unpost") => { const ids = bulkCandidates(action); if (!ids.length) return toast.error(`No ${action === "post" ? "draft" : "posted"} journals available on this page.`); const verb = action === "post" ? "Post" : "Unpost"; if (!window.confirm(`${verb} ${ids.length} journal(s)?\n\nThis operation is atomic. If one journal fails validation, none will be changed.`)) return; bulkLifecycle.mutate({ ids, action }); };
  const allVisibleSelected = visibleRows.length > 0 && visibleRows.every((row) => selected.includes(row.id));
  const toggleAllVisible = () => setSelected(allVisibleSelected ? [] : visibleRows.map((row) => row.id));
  const buOptions=(businessUnits.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const departmentOptions=(departments.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const locationOptions=(locations.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const filterLocationOptions=(filterLocations.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const filterSupplierOptions=(filterSuppliers.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const accountOptions=(accounts.data??[]).map((account:any)=>({id:account.id,label:`${account.account_code} — ${account.account_name}`,keywords:[account.account_code,account.account_name,account.account_type,account.account_subtype]}));

  return <>
    <PageHeader title="Journal Entries" description="Review debit and credit entries, then post or safely unpost eligible journals." actions={<div className="flex flex-wrap gap-2">{canBulkManage && <><Button variant="outline" loading={bulkLifecycle.isPending} onClick={() => runBulk("post")}>Post All</Button><Button variant="outline" loading={bulkLifecycle.isPending} onClick={() => runBulk("unpost")}>Unpost All</Button></>}<Button variant="outline" onClick={() => setBulkImportOpen(true)}>Import Bulk</Button><Button onClick={() => { setPostingDate(todayLocal()); setOpen(true); }}>Create Journal Entry</Button>  <PrintPreviewButton src={printSrc} title="Journal Register" ariaLabel="Preview journal register" label="Print" />
</div>} />
    <div className="grid gap-3 sm:grid-cols-3"><Card><div className="text-xs font-medium uppercase tracking-wide text-slate-500">Filtered Journals</div><div className="mt-1 text-xl font-semibold">{q.data?.total_items ?? 0}</div></Card><Card><div className="text-xs font-medium uppercase tracking-wide text-slate-500">Filtered Debit</div><div className="mt-1 text-xl font-semibold tabular-nums">{filteredJournalTotals ? filteredJournalTotals.debit.toLocaleString("id-ID",{minimumFractionDigits:2}) : "Awaiting backend totals"}</div><div className="mt-1 text-[11px] text-slate-400">Page {visibleTotals.debit.toLocaleString("id-ID",{minimumFractionDigits:2})}</div></Card><Card><div className="text-xs font-medium uppercase tracking-wide text-slate-500">Filtered Credit</div><div className="mt-1 text-xl font-semibold tabular-nums">{filteredJournalTotals ? filteredJournalTotals.credit.toLocaleString("id-ID",{minimumFractionDigits:2}) : "Awaiting backend totals"}</div><div className="mt-1 text-[11px] text-slate-400">Page {visibleTotals.credit.toLocaleString("id-ID",{minimumFractionDigits:2})}</div></Card></div>
    <Card><div className="mb-4 grid gap-3 items-end md:grid-cols-[minmax(260px,1fr)_170px_240px_260px]"><div><label className="mb-1 block text-xs font-medium text-slate-600">Search</label><input className="h-10 w-full rounded border px-3" placeholder="Journal, document, or description" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} /></div><div><label className="block text-xs font-medium text-slate-600 mb-1">Status</label><select className="h-10 w-full rounded border px-3" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}><option value="">All statuses</option><option>DRAFT</option><option>POSTED</option><option>VOID</option></select></div><div><SearchableSelect label="Location" value={filterLocationId} disabled={filterLocations.isLoading} placeholder={filterLocations.isLoading ? "Loading locations..." : "Type location code or name..."} options={filterLocationOptions} onChange={(id) => { setFilterLocationId(id); setPage(1); }} /></div><div><SearchableSelect label="Supplier" value={filterSupplierId} disabled={filterSuppliers.isLoading} placeholder={filterSuppliers.isLoading ? "Loading suppliers..." : "Type supplier code or name..."} options={filterSupplierOptions} onChange={(id) => { setFilterSupplierId(id); setPage(1); }} /></div></div>
      <Table className="min-w-[850px]" containerClassName="border-0 shadow-none"><THead><TR className="whitespace-nowrap"><TH className="w-10"><input type="checkbox" aria-label="Select all journals on this page" checked={allVisibleSelected} onChange={toggleAllVisible} /></TH><TH>Journal</TH><TH>Date</TH><TH>Document</TH><TH>Description</TH><TH numeric>Amount</TH><TH>Status</TH><TH numeric>Actions</TH></TR></THead><TBody>{visibleRows.map((x: any) => <TR key={x.id} className="whitespace-nowrap"><TD><input type="checkbox" aria-label={`Select ${x.journal_number}`} checked={selected.includes(x.id)} onChange={() => setSelected((current) => current.includes(x.id) ? current.filter((value) => value !== x.id) : [...current, x.id])} /></TD><TD><TableCellStack primary={x.journal_number} secondary={x.reference_type?.replaceAll("_", " ")}/></TD><TD>{x.journal_date}</TD><TD className="font-medium">{sourceDocumentPath(x.reference_type, x.reference_id) ? <Link className="text-emerald-700 hover:underline" to={sourceDocumentPath(x.reference_type, x.reference_id)!} state={{ returnTo: `/journal-entries/${x.id}` }} title="Open source document">{x.reference_number || "Open Source"}</Link> : x.reference_number || "—"}</TD><TD className="max-w-[280px]"><span className="block truncate" title={x.description || undefined}>{x.description || "—"}</span></TD><TD numeric className="font-semibold">{Number(x.total_debit).toLocaleString("id-ID", { minimumFractionDigits: 2 })}</TD><TD>{x.status}</TD><TD><div className="flex justify-end gap-2"><Button size="xs" variant="outline" onClick={() => nav(`/journal-entries/${x.id}`)}>View</Button>{x.allowed_actions?.can_post&&<Button size="xs" loading={lifecycle.isPending} onClick={()=>lifecycle.mutate({id:x.id,action:"post"})}>Post</Button>}{x.allowed_actions?.can_unpost&&<Button size="xs" variant="outline" loading={lifecycle.isPending} onClick={()=>lifecycle.mutate({id:x.id,action:"unpost"})}>Unpost</Button>}{x.allowed_actions?.can_void_source_payment&&<Button size="xs" variant="danger" loading={voidSourcePayment.isPending} onClick={()=>{if(window.confirm(`Void payment ${x.reference_number} and its draft journal ${x.journal_number}? This releases the invoice reservation and keeps both records as VOID.`))voidSourcePayment.mutate(x.reference_id)}}>Void Payment</Button>}</div></TD></TR>)}</TBody></Table><div className="mt-4 flex justify-end gap-2"><Button variant="outline" disabled={!q.data?.has_previous} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" disabled={!q.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button></div></Card>

    <JournalBulkImportDialog open={bulkImportOpen} onOpenChange={setBulkImportOpen} onImported={refreshFinance} />

    <Dialog open={open} onOpenChange={setOpen}><DialogContent className="max-w-6xl max-h-[92vh]"><DialogHeader className="py-3"><DialogTitle>Create Journal Entry</DialogTitle></DialogHeader><DialogBody className="space-y-3 overflow-y-auto py-3">
      <div className="grid gap-x-3 gap-y-2 md:grid-cols-3">
        <label className="text-sm font-medium">Posting Date<Input className="mt-1" type="date" min={todayLocal()} value={postingDate} onChange={(e) => setPostingDate(e.target.value)} /></label>
        <label className="text-sm font-medium">Document Number<Input className="mt-1" placeholder="PAYROLL-2026-08" value={documentNumber} onChange={(e) => setDocumentNumber(e.target.value)} /></label>
        <label className="text-sm font-medium">Description<Input className="mt-1" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <SearchableSelect label="Business Unit" required value={businessUnitId} placeholder="Type business unit..." options={buOptions} onChange={changeBusinessUnit}/>
        <SearchableSelect label="Department" value={departmentId} disabled={!businessUnitId} placeholder="Type department..." options={departmentOptions} onChange={setDepartmentId}/>
        <SearchableSelect label="Work Location" required value={locationId} disabled={!businessUnitId} placeholder="Type location..." options={locationOptions} onChange={setLocationId}/>
      </div>
      <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">Organization context applies to every journal line.</div>
      <div className="max-h-[42vh] overflow-auto rounded-lg border"><table className="min-w-[820px] w-full table-fixed text-sm"><thead className="sticky top-0 z-10 bg-slate-50"><tr><th className="w-[36%] px-2 py-2 text-left">Account</th><th className="w-[28%] px-2 py-2 text-left">Line Description</th><th className="w-[14%] px-2 py-2 text-right">Debit</th><th className="w-[14%] px-2 py-2 text-right">Credit</th><th className="w-[8%]" /></tr></thead><tbody>{lines.map((line, index) => <tr key={index} className="border-t"><td className="px-1.5 py-1"><SearchableSelect value={line.account_id || undefined} placeholder="Type account code or name..." options={accountOptions} maxOptions={1000} onChange={(value)=>updateLine(index,{account_id:value??0})}/></td><td className="px-1.5 py-1"><Input value={line.description} onChange={(e) => updateLine(index, { description: e.target.value })} /></td><td className="px-1.5 py-1"><CurrencyInput value={line.debit} onValueChange={(value) => updateLine(index, { debit: value, credit: value > 0 ? 0 : line.credit })} /></td><td className="px-1.5 py-1"><CurrencyInput value={line.credit} onValueChange={(value) => updateLine(index, { credit: value, debit: value > 0 ? 0 : line.debit })} /></td><td className="px-1.5 py-1"><Button type="button" size="xs" variant="danger" disabled={lines.length <= 2} onClick={() => setLines(lines.filter((_, i) => i !== index))}>Remove</Button></td></tr>)}</tbody></table></div>
      <div className="flex items-center justify-between gap-3"><Button type="button" size="sm" variant="outline" onClick={() => setLines([...lines, blankLine()])}>Add Line</Button><div className={`flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border px-3 py-2 text-xs ${balanced ? "bg-emerald-50" : "bg-amber-50"}`}><span>Debit: <strong>{totals.debit.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></span><span>Credit: <strong>{totals.credit.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></span><span>Difference: <strong>{Math.abs(totals.debit - totals.credit).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></span></div></div>
    </DialogBody><DialogFooter><Button variant="outline" onClick={() => setOpen(false)}>Cancel</Button><Button loading={save.isPending} disabled={!valid} onClick={createJournalEntry}>Create Draft Journal</Button></DialogFooter></DialogContent></Dialog>
  </>;
}
