import { journalFilterParams } from "./journalFilters";
import { journalAccountingLabel, journalAllowsBulk } from "./journalState";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { SlidersHorizontal } from "lucide-react";
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
import { todayLocal } from "@/utils/dateConstraints";
import { bulkJournalAction, createJournal, journalAction, listJournals, getJournalScope, getJournalCopyTemplate } from "./api";
import { sourceDocumentPath } from "./sourceDocument";
import { paymentAction } from "@/modules/finance/payments/api";
import useAuthorization from "@/hooks/useAuthorization";

import useFormRecovery from "@/hooks/useFormRecovery";
import FormRecoveryActions from "@/components/form/FormRecoveryActions";

type Line = { account_id: number; debit: number; credit: number; description: string; department_id?: number | null; supplier_id?: number | null };
const blankLine = (): Line => ({ account_id: 0, debit: 0, credit: 0, description: "" });

type JournalInput = { copiedFromId?: number; postingDate: string; documentNumber: string; description: string; businessUnitId?: number; departmentId?: number; locationId?: number; lines: Line[] };
const validInput = (v: unknown): v is JournalInput => { const x = v as JournalInput; return !!x && typeof x.postingDate === "string" && typeof x.documentNumber === "string" && typeof x.description === "string" && Array.isArray(x.lines) && x.lines.every(l => typeof l.account_id === "number" && typeof l.debit === "number" && typeof l.credit === "number" && typeof l.description === "string"); };

export default function JournalListPage() {
  const nav = useNavigate();
  const [urlFilters] = useSearchParams();
  const appliedQuery = useRef<string | null>(null);
  const [dateFrom,setDateFrom] = useState("");
  const [dateTo,setDateTo] = useState("");
  const [filterAccountId,setFilterAccountId] = useState<number>();
  const [filterDepartmentId,setFilterDepartmentId] = useState<number>();
  const [referenceType,setReferenceType] = useState("");
  const [balanceState,setBalanceState] = useState("ALL");
  const [differenceAmount,setDifferenceAmount] = useState("");
  const client = useQueryClient();
  const { isSuperuser } = useAuthorization();
  const canBulkManage = isSuperuser();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => Number(window.localStorage.getItem("journal-page-size")) === 100 ? 100 : 50);
  const [showFilters, setShowFilters] = useState(false);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [filterUnitId, setFilterUnitId] = useState<number>();
  const [scopeReady, setScopeReady] = useState(false);
  const [copiedFromId, setCopiedFromId] = useState<number>();
  const scope = useQuery({ queryKey: ["journal-scope"], queryFn: getJournalScope });
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
  const recovery = useFormRecovery("journal:create", { copiedFromId, postingDate, documentNumber, description, businessUnitId, departmentId, locationId, lines }, open, validInput);
  const openCreate = () => {
    const saved = recovery.load();
    if (saved) { setCopiedFromId(saved.copiedFromId); setPostingDate(saved.postingDate); setDocumentNumber(saved.documentNumber); setDescription(saved.description); setBusinessUnitId(saved.businessUnitId); setDepartmentId(saved.departmentId); setLocationId(saved.locationId); setLines(saved.lines); recovery.notifyRestored(); }
    if (!saved) { setCopiedFromId(undefined); setBusinessUnitId(filterUnitId); setLocationId(filterLocationId ?? scope.data?.default_location_id ?? undefined); }
    setOpen(true);
  };
  const discardInput = () => { recovery.clear(); setCopiedFromId(undefined); setOpen(false); setPostingDate(todayLocal()); setDocumentNumber(""); setDescription("Salary journal"); setBusinessUnitId(undefined); setDepartmentId(undefined); setLocationId(undefined); setLines([blankLine(), blankLine()]); };
  const [selected, setSelected] = useState<number[]>([]);

  const filterParams = journalFilterParams({search,status,business_unit_id:filterUnitId,location_id:filterLocationId,supplier_id:filterSupplierId,
    date_from:dateFrom,date_to:dateTo,account_id:filterAccountId,department_id:filterDepartmentId,reference_type:referenceType,
    balance_state:balanceState,difference_amount:differenceAmount});
  const q = useQuery({ queryKey:["journal-entries",page,pageSize,filterParams],queryFn:()=>listJournals({...filterParams,page,page_size:pageSize}),enabled:scopeReady });
  const filterAccounts = useQuery({queryKey:["journal-filter-accounts"],queryFn:()=>getAllAccountLookup(),enabled:showFilters});
  const filterDepartments = useQuery({queryKey:["journal-filter-departments",filterUnitId,filterLocationId],queryFn:()=>listDepartments({business_unit_id:filterUnitId,location_id:filterLocationId}),enabled:showFilters});
  const accounts = useQuery({ queryKey: ["journal-account-lookup"], queryFn: () => getAllAccountLookup({ is_posting: true, is_active: true }), enabled: open });
  const businessUnits = useQuery({ queryKey: ["business-units", "manual-journal", "active"], queryFn: () => filterBusinessUnits({ is_active: true }), enabled: open });
  const departments = useQuery({ queryKey: ["journal-departments", businessUnitId, locationId], queryFn: () => listDepartments({ business_unit_id: businessUnitId, location_id: locationId, is_active: true }), enabled: open && Boolean(businessUnitId && locationId) });
  const locations = useQuery({ queryKey: ["journal-locations", businessUnitId], queryFn: () => listLocations({ business_unit_id: businessUnitId, is_active: true }), enabled: open && Boolean(businessUnitId) });
  const filterLocations = useQuery({ queryKey: ["journal-filter-locations", "active"], queryFn: () => listLocations({ is_active: true }) });
  const filterSuppliers = useQuery({ queryKey: ["journal-filter-suppliers"], queryFn: () => supplierApi.lookup("", 100) });

  useEffect(() => {
    const query = urlFilters.toString();
    if (!scope.data || appliedQuery.current===query) return;
    appliedQuery.current=query;
    const unit=Number(urlFilters.get("business_unit_id"))||undefined;
    const location=Number(urlFilters.get("location_id"))||undefined;
    setFilterUnitId(!scope.data.location_locked&&urlFilters.get("business_unit_id")==="all"?undefined:unit&&scope.data.units.some(row=>row.id===unit)?unit:scope.data.default_business_unit_id??undefined);
    setFilterLocationId(scope.data.location_locked?scope.data.default_location_id??undefined:urlFilters.get("location_id")==="all"?undefined:location&&scope.data.locations.some(row=>row.id===location)?location:scope.data.default_location_id??undefined);
    setBusinessUnitId(scope.data.default_business_unit_id??undefined);
    setLocationId(scope.data.default_location_id??undefined);
    setSearch(urlFilters.get("search")||"");setStatus(urlFilters.get("status")||"");
    setDateFrom(urlFilters.get("date_from")||"");setDateTo(urlFilters.get("date_to")||"");
    setFilterAccountId(Number(urlFilters.get("account_id"))||undefined);
    setFilterDepartmentId(Number(urlFilters.get("department_id"))||undefined);
    setFilterSupplierId(Number(urlFilters.get("supplier_id"))||undefined);
    setReferenceType(urlFilters.get("reference_type")||"");
    setBalanceState(urlFilters.get("balance_state")||"ALL");setDifferenceAmount(urlFilters.get("difference_amount")||"");
    if(query)setShowFilters(true);
    setPage(1);setScopeReady(true);
  }, [scope.data,urlFilters]);
  useEffect(() => { setSelected([]); }, [page,pageSize,search,status,filterUnitId,filterLocationId,filterSupplierId,dateFrom,dateTo,filterAccountId,filterDepartmentId,referenceType,balanceState,differenceAmount]);
  useEffect(() => window.localStorage.setItem("journal-page-size", String(pageSize)), [pageSize]);
  useEffect(() => { if (open && !businessUnitId && businessUnits.data?.length === 1) setBusinessUnitId(businessUnits.data[0].id); }, [open, businessUnitId, businessUnits.data]);

  const totals = useMemo(() => lines.reduce((sum, line) => ({ debit: sum.debit + line.debit, credit: sum.credit + line.credit }), { debit: 0, credit: 0 }), [lines]);
  const validLines = lines.filter((line) => line.account_id > 0 && (line.debit > 0 || line.credit > 0));
  const refreshFinance = useCallback(() => { client.invalidateQueries({ queryKey: ["journal-entries"] }); client.invalidateQueries({ queryKey: ["journal-entry"] }); client.invalidateQueries({ queryKey: ["general-ledger"] }); client.invalidateQueries({ queryKey: ["trial-balance"] }); client.invalidateQueries({ queryKey: ["accounts-payable-aging"] }); client.invalidateQueries({ queryKey: ["ap-reporting"] }); client.invalidateQueries({ queryKey: ["supplier-invoices"] }); client.invalidateQueries({ queryKey: ["supplier-invoice"] }); client.invalidateQueries({ queryKey: ["eligible-payment-invoices"] }); client.invalidateQueries({ queryKey: ["eligible-payment-suppliers"] }); client.invalidateQueries({ queryKey: ["payments"] }); client.invalidateQueries({ queryKey: ["payment"] }); client.invalidateQueries({ queryKey: ["finance-dashboard"] }); client.invalidateQueries({ queryKey: ["balance-sheet"] }); client.invalidateQueries({ queryKey: ["profit-loss"] }); }, [client]);
  const voidSourcePayment = useMutation({ mutationFn: (paymentId: number) => paymentAction(paymentId, "void"), onSuccess: () => { toast.success("Payment and its draft journal were voided."); refreshFinance(); }, onError: (error: any) => toast.error(error?.response?.data?.detail || "Payment could not be voided.") });
  const lifecycle = useMutation({ mutationFn: ({ id, action }: { id: number; action: "post" | "unpost" }) => journalAction(id, action), onSuccess: (_, vars) => { toast.success(vars.action === "post" ? "Journal posted." : "Journal returned to draft."); refreshFinance(); }, onError: (error: any) => toast.error(error?.response?.data?.detail || "Journal action failed.") });
  const bulkLifecycle = useMutation({ mutationFn: ({ ids, action }: { ids: number[]; action: "post" | "unpost" }) => bulkJournalAction(ids, action), onSuccess: (result) => { toast.success(`${result.processed} journal(s) changed to ${result.status}.`); setSelected([]); refreshFinance(); }, onError: (error: any) => toast.error(error?.response?.data?.detail || "Bulk journal action failed. No journals were changed.") });
  const save = useMutation({ mutationFn: () => createJournal({ copied_from_journal_id: copiedFromId, posting_date: postingDate, document_type: "MANUAL_JOURNAL", document_number: documentNumber.trim(), reference_type: "MANUAL", reference_id: 0, description: description.trim() || undefined, business_unit_id: businessUnitId!, department_id: departmentId ?? null, location_id: locationId ?? null, lines: validLines.map((line) => ({ ...line, description: line.description || undefined, business_unit_id: businessUnitId, department_id: line.department_id === undefined ? departmentId ?? null : line.department_id, location_id: locationId ?? null })) }), onSuccess: (journal) => { toast.success("Journal entry created."); setCopiedFromId(undefined); recovery.clear(); setOpen(false); setPostingDate(todayLocal()); setDocumentNumber(""); setDescription("Salary journal"); setDepartmentId(undefined); setLocationId(undefined); setBusinessUnitId(businessUnits.data?.length === 1 ? businessUnits.data[0].id : undefined); setLines([blankLine(), blankLine()]); refreshFinance(); nav(`/journal-entries/${journal.id}`); }, onError: (error: any) => toast.error(typeof error?.response?.data?.detail === "string" ? error.response.data.detail : "Journal entry could not be created.") });
  const copy = useMutation({ mutationFn: getJournalCopyTemplate, onSuccess: template => {
    const saved = recovery.load();
    if (saved && !window.confirm("Replace the saved journal form with this copy?")) return;
    setCopiedFromId(template.copied_from_journal_id); setPostingDate(todayLocal());
    setDocumentNumber(""); setDescription(template.description || "");
    setBusinessUnitId(template.business_unit_id ?? scope.data?.locations.find(row => row.id === template.location_id)?.business_unit_id ?? undefined);
    setLocationId(template.location_id ?? undefined); setDepartmentId(template.department_id ?? undefined);
    setLines(template.lines.map(line => ({ account_id: line.account_id, debit: Number(line.debit), credit: Number(line.credit), description: line.description || "", department_id: line.department_id, supplier_id: line.supplier_id })));
    setOpen(true);
  }, onError: () => toast.error("Journal could not be copied.") });
  const updateLine = (index: number, patch: Partial<Line>) => setLines(lines.map((line, i) => i === index ? { ...line, ...patch } : line));
  const balanced = totals.debit > 0 && Math.abs(totals.debit - totals.credit) < 0.005;
  const valid = Boolean(documentNumber.trim() && businessUnitId && locationId && validLines.length >= 1 && postingDate && (!departmentId || departments.data?.some(department => department.id === departmentId)));
  const changeBusinessUnit = (value?: number) => { setBusinessUnitId(value); setDepartmentId(undefined); setLocationId(undefined); };
  const createJournalEntry = () => { if (!locationId) return toast.error("Select a work location."); save.mutate(); };
  const visibleRows: any[] = useMemo(() => q.data?.items ?? [], [q.data?.items]);
  const visibleTotals = useMemo(() => visibleRows.reduce((sum, row) => ({ debit: sum.debit + Number(row.total_debit || 0), credit: sum.credit + Number(row.total_credit || 0) }), { debit: 0, credit: 0 }), [visibleRows]);
  const filteredJournalTotals = q.data?.summary?.total_debit != null && q.data?.summary?.total_credit != null
    ? { debit: Number(q.data.summary.total_debit), credit: Number(q.data.summary.total_credit) }
    : null;
  const printQuery = new URLSearchParams(Object.fromEntries(Object.entries(filterParams).map(([key,value])=>[key,String(value)]))).toString();
  const printSrc = `/journal/register/print${printQuery ? `?${printQuery}` : ""}`;
  const selectedRows = visibleRows.filter((row) => selected.includes(row.id));
  const bulkCandidates = (action: "post" | "unpost") => { const source = selectedRows.length ? selectedRows : visibleRows; return source.filter((row) => journalAllowsBulk(row, action)).map((row) => row.id); };
  const runBulk = (action: "post" | "unpost") => { const ids = bulkCandidates(action); if (!ids.length) return toast.error(`No ${action === "post" ? "draft" : "posted"} journals available on this page.`); const verb = action === "post" ? "Post" : "Unpost"; if (!window.confirm(`${verb} ${ids.length} journal(s)?\n\nThis operation is atomic. If one journal fails validation, none will be changed.`)) return; bulkLifecycle.mutate({ ids, action }); };
  const allVisibleSelected = visibleRows.length > 0 && visibleRows.every((row) => selected.includes(row.id));
  const toggleAllVisible = () => setSelected(allVisibleSelected ? [] : visibleRows.map((row) => row.id));
  const buOptions=(businessUnits.data??[]).filter(item => !scope.data?.location_locked || scope.data.units.some(unit => unit.id === item.id)).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const departmentOptions=(departments.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const locationOptions=(locations.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const filterLocationOptions=(scope.data?.locations??filterLocations.data??[]).filter(item => !filterUnitId || item.business_unit_id === filterUnitId).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const filterSupplierOptions=(filterSuppliers.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const accountOptions=(accounts.data??[]).map((account:any)=>({id:account.id,label:`${account.account_code} — ${account.account_name}`,keywords:[account.account_code,account.account_name,account.account_type,account.account_subtype]}));

  return <DataWorkspace area="Accounting">
    <PageHeader title="Journal Entries" description="Complete balanced draft journals are reflected in accounting while the period is open. Period closing finalizes drafts and locks the period; posted journals remain posted." actions={<div className="flex flex-wrap gap-2">{canBulkManage && <><Button variant="outline" loading={bulkLifecycle.isPending} onClick={() => runBulk("post")}>Post All</Button><Button variant="outline" loading={bulkLifecycle.isPending} onClick={() => runBulk("unpost")}>Unpost All</Button></>}<Button variant="outline" onClick={() => setBulkImportOpen(true)}>Import Bulk</Button><Button disabled={!scopeReady} onClick={openCreate}>Create Journal Entry</Button>  <PrintPreviewButton src={printSrc} title="Journal Register" ariaLabel="Preview journal register" label="Print" />
</div>} />
    <div className="flex flex-wrap gap-1" aria-label="Journal business unit">
      {!scope.data?.location_locked && <Button size="sm" variant={!filterUnitId ? "primary" : "outline"} onClick={() => { setFilterUnitId(undefined); setFilterLocationId(undefined); setFilterDepartmentId(undefined); setPage(1); }}>All units</Button>}
      {scope.data?.units.map(unit => <Button key={unit.id} size="sm" variant={filterUnitId === unit.id ? "primary" : "outline"} onClick={() => { setFilterDepartmentId(undefined); setFilterUnitId(unit.id); if (!scope.data.location_locked) setFilterLocationId(undefined); setPage(1); }}>{unit.name}</Button>)}
    </div>
    {scope.isError && <p role="alert" className="text-sm text-red-700">Journal location scope could not be loaded.</p>}
    <div className="workspace-summary"><Card><div className="text-xs font-medium uppercase tracking-wide text-slate-500">Filtered Journals</div><div className="mt-1 text-xl font-semibold">{q.data?.total_items ?? 0}</div></Card><Card><div className="text-xs font-medium uppercase tracking-wide text-slate-500">Filtered Debit</div><div className="mt-1 text-xl font-semibold tabular-nums">{filteredJournalTotals ? filteredJournalTotals.debit.toLocaleString("id-ID",{minimumFractionDigits:2}) : "Awaiting backend totals"}</div><div className="mt-1 text-[11px] text-slate-400">Page {visibleTotals.debit.toLocaleString("id-ID",{minimumFractionDigits:2})}</div></Card><Card><div className="text-xs font-medium uppercase tracking-wide text-slate-500">Filtered Credit</div><div className="mt-1 text-xl font-semibold tabular-nums">{filteredJournalTotals ? filteredJournalTotals.credit.toLocaleString("id-ID",{minimumFractionDigits:2}) : "Awaiting backend totals"}</div><div className="mt-1 text-[11px] text-slate-400">Page {visibleTotals.credit.toLocaleString("id-ID",{minimumFractionDigits:2})}</div></Card><Card><div className="text-xs font-medium uppercase tracking-wide text-slate-500">Filtered Difference</div><div className="mt-1 font-semibold tabular-nums">{filteredJournalTotals?(filteredJournalTotals.debit-filteredJournalTotals.credit).toLocaleString("id-ID",{minimumFractionDigits:2}):"—"}</div></Card></div>
    <Card className="workspace-data p-0"><div className="workspace-toolbar mb-2 flex flex-wrap items-end gap-2">
      <label className="min-w-[240px] flex-1 text-xs font-medium text-slate-600">Search
        <input className="mt-1 h-9 w-full rounded border px-3" placeholder="Journal, document, or description" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
      </label>
      <label className="min-w-[145px] text-xs font-medium text-slate-600">Status
        <select className="mt-1 h-9 w-full rounded border px-3" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}><option value="">All statuses</option><option>DRAFT</option><option>POSTED</option><option>VOID</option></select>
      </label>
      <Button type="button" size="sm" variant="outline" aria-expanded={showFilters} onClick={() => setShowFilters(value => !value)}>
        <SlidersHorizontal size={15}/> Filters{[filterLocationId,filterSupplierId,dateFrom,dateTo,filterAccountId,filterDepartmentId,referenceType,balanceState!=="ALL",differenceAmount].filter(Boolean).length ? ` (${[filterLocationId,filterSupplierId,dateFrom,dateTo,filterAccountId,filterDepartmentId,referenceType,balanceState!=="ALL",differenceAmount].filter(Boolean).length})` : ""}
      </Button>
    </div>
    {showFilters && <div className="mb-2 grid gap-2 border-t border-slate-100 pt-2 md:grid-cols-3">
      <label className="text-xs">From Date<input aria-label="From Date" className="mt-1 h-9 w-full rounded border px-2" type="date" value={dateFrom} onChange={e=>{setDateFrom(e.target.value);setPage(1);}}/></label>
      <label className="text-xs">To Date<input aria-label="To Date" className="mt-1 h-9 w-full rounded border px-2" type="date" value={dateTo} onChange={e=>{setDateTo(e.target.value);setPage(1);}}/></label>
      <label className="text-xs">Balance<select aria-label="Journal balance" className="mt-1 h-9 w-full rounded border px-2" value={balanceState} onChange={e=>{setBalanceState(e.target.value);setPage(1);}}><option value="ALL">All</option><option value="BALANCED">Balanced</option><option value="UNBALANCED">Unbalanced</option></select></label>
      <label className="text-xs">Difference amount<input aria-label="Difference amount" className="mt-1 h-9 w-full rounded border px-2 text-right" type="number" min="0" step="0.01" placeholder="Any difference" value={differenceAmount} onChange={e=>{setDifferenceAmount(e.target.value);setPage(1);}}/></label>
      <SearchableSelect label="Account" value={filterAccountId} placeholder="Account code or name..." options={(filterAccounts.data??[]).map(row=>({id:row.id,label:`${row.account_code} — ${row.account_name}`}))} onChange={id=>{setFilterAccountId(id);setPage(1);}}/>
      <SearchableSelect label="Department" value={filterDepartmentId} placeholder="Department name..." options={(filterDepartments.data??[]).map(row=>({id:row.id,label:row.name}))} onChange={id=>{setFilterDepartmentId(id);setPage(1);}}/>
      <label className="text-xs">Source type<select aria-label="Source type" className="mt-1 h-9 w-full rounded border px-2" value={referenceType} onChange={e=>{setReferenceType(e.target.value);setPage(1);}}><option value="">All sources</option>{Array.from(new Set<string>([...(q.data?.reference_types??[]),...(referenceType?[referenceType]:[])])).map(value=><option key={value} value={value}>{value.replaceAll("_"," ")}</option>)}</select></label>
      <SearchableSelect label="Location" value={filterLocationId} disabled={scope.isLoading || scope.data?.location_locked} placeholder={filterLocations.isLoading ? "Loading locations..." : "Type location code or name..."} options={filterLocationOptions} onChange={(id) => { setFilterLocationId(id); setFilterDepartmentId(undefined); setPage(1); }} />
      <SearchableSelect label="Supplier" value={filterSupplierId} disabled={filterSuppliers.isLoading} placeholder={filterSuppliers.isLoading ? "Loading suppliers..." : "Type supplier code or name..."} options={filterSupplierOptions} onChange={(id) => { setFilterSupplierId(id); setPage(1); }} />
    </div>}
      <Table stickyHeader className="workspace-journal-table min-w-[850px]" containerClassName="workspace-table-scroll max-h-[60vh] overflow-auto border-0 shadow-none print:max-h-none print:overflow-visible"><THead><TR className="whitespace-nowrap"><TH className="w-10"><input type="checkbox" aria-label="Select all journals on this page" checked={allVisibleSelected} onChange={toggleAllVisible} /></TH><TH>Journal</TH><TH>Date</TH><TH>Document</TH><TH>Description</TH><TH numeric>Debit</TH><TH numeric>Credit</TH><TH numeric>Difference</TH><TH>Status</TH><TH numeric>Actions</TH></TR></THead><TBody>{q.isLoading && <TR><TD colSpan={10} className="py-10 text-center text-slate-500">Loading journals…</TD></TR>}{q.isError && <TR><TD colSpan={10} className="py-10 text-center text-red-700">Journals could not be loaded. Use Refresh to try again.</TD></TR>}{!q.isLoading && !q.isError && visibleRows.length === 0 && <TR><TD colSpan={10} className="py-10 text-center text-slate-500">No journals match these filters.</TD></TR>}{visibleRows.map((x: any) => <TR key={x.id} className="whitespace-nowrap"><TD><input type="checkbox" aria-label={`Select ${x.journal_number}`} checked={selected.includes(x.id)} onChange={() => setSelected((current) => current.includes(x.id) ? current.filter((value) => value !== x.id) : [...current, x.id])} /></TD><TD><TableCellStack primary={x.journal_number} secondary={x.reference_type?.replaceAll("_", " ")}/></TD><TD>{x.journal_date}</TD><TD className="font-medium">{sourceDocumentPath(x.reference_type, x.reference_id) ? <Link className="text-emerald-700 hover:underline" to={sourceDocumentPath(x.reference_type, x.reference_id)!} state={{ returnTo: `/journal-entries/${x.id}` }} title="Open source document">{x.reference_number || "Open Source"}</Link> : x.reference_number || "—"}</TD><TD className="max-w-[280px]"><span className="block truncate" title={x.description || undefined}>{x.description || "—"}</span></TD><TD numeric className="font-semibold">{Number(x.total_debit).toLocaleString("id-ID", { minimumFractionDigits: 2 })}</TD><TD numeric className="font-semibold">{Number(x.total_credit).toLocaleString("id-ID",{minimumFractionDigits:2})}</TD><TD numeric className={Number(x.difference)!==0?"font-semibold text-red-700":"text-slate-500"}>{Number(x.difference??Number(x.total_debit)-Number(x.total_credit)).toLocaleString("id-ID",{minimumFractionDigits:2})}</TD><TD><span>{x.status}</span><span className={`ml-2 text-xs ${x.period_locked?"text-slate-500":x.accounting_recognized?"text-emerald-700":"text-amber-700"}`} title={x.recognition_reason??x.period_name??undefined}>{journalAccountingLabel(x)}</span></TD><TD><div className="flex justify-end gap-2"><Button size="xs" variant="outline" onClick={() => nav(`/journal-entries/${x.id}`)}>View</Button>{x.allowed_actions?.can_copy && <Button size="xs" variant="outline" loading={copy.isPending} onClick={() => copy.mutate(x.id)}>Copy</Button>}{x.allowed_actions?.can_post&&<Button size="xs" loading={lifecycle.isPending} onClick={()=>lifecycle.mutate({id:x.id,action:"post"})}>Post</Button>}{x.allowed_actions?.can_unpost&&<Button size="xs" variant="outline" loading={lifecycle.isPending} onClick={()=>lifecycle.mutate({id:x.id,action:"unpost"})}>Unpost</Button>}{x.allowed_actions?.can_void_source_payment&&<Button size="xs" variant="danger" loading={voidSourcePayment.isPending} onClick={()=>{if(window.confirm(`Void payment ${x.reference_number} and its draft journal ${x.journal_number}? This releases the invoice reservation and keeps both records as VOID.`))voidSourcePayment.mutate(x.reference_id)}}>Void Payment</Button>}</div></TD></TR>)}</TBody></Table><div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2 text-xs"><label>Rows per page <select className="ml-1 rounded border border-slate-300 bg-white px-2 py-1" value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }}><option value={50}>50</option><option value={100}>100</option></select></label><div className="flex items-center gap-2"><span>{q.data?.total_items ?? 0} journals · Page {page} of {Math.max(q.data?.total_pages ?? 0, 1)}</span><Button size="sm" variant="outline" disabled={!q.data?.has_previous} onClick={() => setPage(page - 1)}>Previous</Button><Button size="sm" variant="outline" disabled={!q.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button></div></div></Card>

    <JournalBulkImportDialog open={bulkImportOpen} onOpenChange={setBulkImportOpen} onImported={refreshFinance} />

    <Dialog open={open} onOpenChange={next => { if (!save.isPending) setOpen(next); }}><DialogContent className="max-w-6xl max-h-[92vh]"><DialogHeader className="py-3"><DialogTitle>{copiedFromId ? "Copy Journal Entry" : "Create Journal Entry"}</DialogTitle></DialogHeader><DialogBody className="space-y-3 overflow-y-auto py-3">
      <div className="grid gap-x-3 gap-y-2 md:grid-cols-3">
        <label className="text-sm font-medium">Posting Date<Input className="mt-1" type="date" data-accounting-date="true" value={postingDate} onChange={(e) => setPostingDate(e.target.value)} /></label>
        <label className="text-sm font-medium">Document Number<Input className="mt-1" placeholder="PAYROLL-2026-08" value={documentNumber} onChange={(e) => setDocumentNumber(e.target.value)} /></label>
        <label className="text-sm font-medium">Description<Input className="mt-1" value={description} onChange={(e) => setDescription(e.target.value)} /></label>
        <SearchableSelect label="Business Unit" required value={businessUnitId} placeholder="Type business unit..." options={buOptions} onChange={changeBusinessUnit}/>
        <SearchableSelect label="Work Location" required value={locationId} disabled={!businessUnitId} placeholder="Type location..." options={locationOptions} onChange={value => { setLocationId(value); setDepartmentId(undefined); }}/>
        <SearchableSelect label="Default Department" value={departmentId} disabled={!locationId || departments.isLoading} placeholder={locationId ? "Select department (optional)..." : "Select location first..."} options={departmentOptions} onChange={setDepartmentId}/>
      </div>
      <div className="rounded border border-slate-200 bg-slate-50 px-3 py-2 text-xs text-slate-600">One journal header covers all lines. Unit and location apply to the journal; department can vary per line.</div>
      <div className="max-h-[42vh] overflow-auto rounded-lg border"><table className="min-w-[1050px] w-full table-fixed text-sm"><thead className="sticky top-0 z-10 bg-slate-50"><tr><th className="w-[28%] px-2 py-2 text-left">Account</th><th className="w-[20%] px-2 py-2 text-left">Department</th><th className="w-[24%] px-2 py-2 text-left">Line Description</th><th className="w-[14%] px-2 py-2 text-right">Debit</th><th className="w-[14%] px-2 py-2 text-right">Credit</th><th className="w-[8%]" /></tr></thead><tbody>{lines.map((line, index) => <tr key={index} className="border-t"><td className="px-1.5 py-1"><SearchableSelect value={line.account_id || undefined} placeholder="Type account code or name..." options={accountOptions} maxOptions={1000} onChange={(value)=>updateLine(index,{account_id:value??0})}/></td><td className="px-1.5 py-1"><SearchableSelect value={line.department_id ?? undefined} placeholder={line.department_id === null ? "No department" : departmentId ? `Default: ${departments.data?.find(item => item.id === departmentId)?.name ?? "Department"}` : "Department (optional)"} disabled={!locationId || departments.isLoading} options={departmentOptions} onChange={value => updateLine(index,{department_id:value ?? null})}/></td><td className="px-1.5 py-1"><Input value={line.description} onChange={(e) => updateLine(index, { description: e.target.value })} /></td><td className="px-1.5 py-1"><CurrencyInput value={line.debit} onValueChange={(value) => updateLine(index, { debit: value, credit: value > 0 ? 0 : line.credit })} /></td><td className="px-1.5 py-1"><CurrencyInput value={line.credit} onValueChange={(value) => updateLine(index, { credit: value, debit: value > 0 ? 0 : line.debit })} /></td><td className="px-1.5 py-1"><Button type="button" size="xs" variant="danger" disabled={lines.length <= 1} onClick={() => setLines(lines.filter((_, i) => i !== index))}>Remove</Button></td></tr>)}</tbody></table></div>
      <div className="flex items-center justify-between gap-3"><Button type="button" size="sm" variant="outline" onClick={() => setLines([...lines, blankLine()])}>Add Line</Button><div className={`flex flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border px-3 py-2 text-xs ${balanced ? "bg-emerald-50" : "bg-amber-50"}`}><span>1 journal · {validLines.length} lines</span><span>Debit: <strong>{totals.debit.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></span><span>Credit: <strong>{totals.credit.toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></span><span>Difference: <strong>{Math.abs(totals.debit - totals.credit).toLocaleString(undefined, { minimumFractionDigits: 2 })}</strong></span></div></div>
    </DialogBody><DialogFooter><FormRecoveryActions failed={recovery.failed} disabled={save.isPending} onDiscard={discardInput} /><Button variant="outline" disabled={save.isPending} onClick={() => setOpen(false)}>Close</Button><Button loading={save.isPending} disabled={!valid} onClick={createJournalEntry}>Create Draft Journal</Button></DialogFooter></DialogContent></Dialog>
  </DataWorkspace>;
}

