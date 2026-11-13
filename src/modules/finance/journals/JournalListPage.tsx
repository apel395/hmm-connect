import { journalFilterParams } from "./journalFilters";
import { journalAllowsBulk } from "./journalState";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { AlertTriangle, SlidersHorizontal } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Input from "@/components/ui/Input";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import SearchableSelect from "@/components/form/SearchableSelect";
import JournalBulkImportDialog from "./JournalBulkImportDialog";
import JournalRegisterTable from "./JournalRegisterTable";
import { journalMonthRange, journalSelectedMonth } from "./journalRegisterPeriod";
import { filterBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { supplierApi } from "@/modules/master/suppliers/api/supplierApi";
import { todayLocal } from "@/utils/dateConstraints";
import { bulkJournalAction, createJournal, journalAction, listJournals, getJournalScope, getJournalCopyTemplate } from "./api";
import { paymentAction } from "@/modules/finance/payments/api";
import useAuthorization from "@/hooks/useAuthorization";

import useFormRecovery from "@/hooks/useFormRecovery";
import FormRecoveryActions from "@/components/form/FormRecoveryActions";

type Line = { account_id: number; debit: number; credit: number; description: string; department_id?: number | null; supplier_id?: number | null };
const registerReturnKey = "journal-register-return";

function restoreRegisterFilters(query: string) {
  try {
    const saved = window.sessionStorage.getItem(registerReturnKey);
    window.sessionStorage.removeItem(registerReturnKey);
    const filters = new URLSearchParams(saved ?? "");
    return filters.get("register_query") === query ? filters : new URLSearchParams();
  } catch {
    return new URLSearchParams();
  }
}

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
    const saved = restoreRegisterFilters(query);
    const filters = query && !saved.size ? urlFilters : saved;
    const unit=Number(filters.get("business_unit_id"))||undefined;
    const location=Number(filters.get("location_id"))||undefined;
    setFilterUnitId(!scope.data.location_locked&&filters.get("business_unit_id")==="all"?undefined:unit&&scope.data.units.some(row=>row.id===unit)?unit:scope.data.default_business_unit_id??undefined);
    setFilterLocationId(scope.data.location_locked?scope.data.default_location_id??undefined:filters.get("location_id")==="all"?undefined:location&&scope.data.locations.some(row=>row.id===location)?location:scope.data.default_location_id??undefined);
    setBusinessUnitId(scope.data.default_business_unit_id??undefined);
    setLocationId(scope.data.default_location_id??undefined);
    setSearch(filters.get("search")||"");setStatus(filters.get("status")||"");
    setDateFrom(filters.get("date_from")||"");setDateTo(filters.get("date_to")||"");
    setFilterAccountId(Number(filters.get("account_id"))||undefined);
    setFilterDepartmentId(Number(filters.get("department_id"))||undefined);
    setFilterSupplierId(Number(filters.get("supplier_id"))||undefined);
    setReferenceType(filters.get("reference_type")||"");
    setBalanceState(filters.get("balance_state")||"ALL");setDifferenceAmount(filters.get("difference_amount")||"");
    setShowFilters(saved.size ? filters.get("more_filters") === "1" : Boolean(query));
    setPage(saved.size ? Math.max(1, Number(filters.get("page")) || 1) : 1);setScopeReady(true);
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
  const openJournal = (id: number) => {
    const filters = new URLSearchParams();
    for (const [key, value] of Object.entries(filterParams)) filters.set(key, String(value));
    filters.set("business_unit_id", filterUnitId ? String(filterUnitId) : "all");
    filters.set("location_id", filterLocationId ? String(filterLocationId) : "all");
    filters.set("register_query", urlFilters.toString());
    filters.set("page", String(page));
    filters.set("more_filters", showFilters ? "1" : "0");
    try {
      window.sessionStorage.setItem(registerReturnKey, filters.toString());
    } catch {
      // Keep navigation available when storage is disabled.
    }
    nav(`/journal-entries/${id}`);
  };
  const save = useMutation({ mutationFn: () => createJournal({ copied_from_journal_id: copiedFromId, posting_date: postingDate, document_type: "MANUAL_JOURNAL", document_number: documentNumber.trim(), reference_type: "MANUAL", reference_id: 0, description: description.trim() || undefined, business_unit_id: businessUnitId!, department_id: departmentId ?? null, location_id: locationId ?? null, lines: validLines.map((line) => ({ ...line, description: line.description || undefined, business_unit_id: businessUnitId, department_id: line.department_id === undefined ? departmentId ?? null : line.department_id, location_id: locationId ?? null })) }), onSuccess: (journal) => { toast.success("Journal entry created."); setCopiedFromId(undefined); recovery.clear(); setOpen(false); setPostingDate(todayLocal()); setDocumentNumber(""); setDescription("Salary journal"); setDepartmentId(undefined); setLocationId(undefined); setBusinessUnitId(businessUnits.data?.length === 1 ? businessUnits.data[0].id : undefined); setLines([blankLine(), blankLine()]); refreshFinance(); openJournal(journal.id); }, onError: (error: any) => toast.error(typeof error?.response?.data?.detail === "string" ? error.response.data.detail : "Journal entry could not be created.") });
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
  const bulkCandidates = (action: "post" | "unpost") => selectedRows.filter((row) => journalAllowsBulk(row, action)).map((row) => row.id);
  const runBulk = (action: "post" | "unpost") => { const ids = bulkCandidates(action); if (!ids.length) return toast.error(`No eligible ${action === "post" ? "draft" : "posted"} journals selected.`); const verb = action === "post" ? "Post" : "Unpost"; if (!window.confirm(`${verb} ${ids.length} selected journal(s)?\n\nThis operation is atomic. If one journal fails validation, none will be changed.`)) return; bulkLifecycle.mutate({ ids, action }); };
  const allVisibleSelected = visibleRows.length > 0 && visibleRows.every((row) => selected.includes(row.id));
  const toggleAllVisible = () => setSelected(allVisibleSelected ? [] : visibleRows.map((row) => row.id));
  const buOptions=(businessUnits.data??[]).filter(item => !scope.data?.location_locked || scope.data.units.some(unit => unit.id === item.id)).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const departmentOptions=(departments.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const locationOptions=(locations.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const filterLocationOptions=(scope.data?.locations??filterLocations.data??[]).filter(item => !filterUnitId || item.business_unit_id === filterUnitId).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const filterSupplierOptions=(filterSuppliers.data??[]).map((item:any)=>({id:item.id,label:`${item.code} — ${item.name}`,keywords:[item.code??"",item.name??""]}));
  const accountOptions=(accounts.data??[]).map((account:any)=>({id:account.id,label:`${account.account_code} — ${account.account_name}`,keywords:[account.account_code,account.account_name,account.account_type,account.account_subtype]}));
  const selectedMonth = journalSelectedMonth(dateFrom, dateTo);
  const changeMonth = (month: string) => {
    const range = journalMonthRange(month);
    setDateFrom(range?.from ?? "");
    setDateTo(range?.to ?? "");
    setPage(1);
  };
  const clearJournalFilters = () => {
    setSearch(""); setStatus(""); setDateFrom(""); setDateTo("");
    setReferenceType(""); setBalanceState("ALL"); setDifferenceAmount("");
    setFilterAccountId(undefined); setFilterDepartmentId(undefined); setFilterSupplierId(undefined);
    if (!scope.data?.location_locked) setFilterLocationId(undefined);
    setPage(1);
  };
  const advancedFilterCount = [filterAccountId, filterDepartmentId, filterSupplierId, filterLocationId, balanceState !== "ALL", differenceAmount, dateFrom && !selectedMonth, dateTo && !selectedMonth].filter(Boolean).length;
  const filteredDifference = filteredJournalTotals ? filteredJournalTotals.debit - filteredJournalTotals.credit : null;
  const hasDifference = filteredDifference !== null && Math.abs(filteredDifference) > 0.005;
  const formatAmount = (value: number) => value.toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  return <DataWorkspace area="Accounting" className="journal-register-workspace">
    <PageHeader title="Journal Register" description="Balanced draft journals are recognized while the period is open. Closing the period finalizes and locks its journals." actions={<div className="flex flex-wrap items-center gap-2">
      <div className="flex flex-wrap items-center gap-1 border-r border-slate-200 pr-3" aria-label="Journal business unit">
        {!scope.data?.location_locked && <Button size="sm" variant={!filterUnitId ? "primary" : "outline"} onClick={() => { setFilterUnitId(undefined); setFilterLocationId(undefined); setFilterDepartmentId(undefined); setPage(1); }}>All units</Button>}
        {scope.data?.units.map(unit => <Button key={unit.id} size="sm" variant={filterUnitId === unit.id ? "primary" : "outline"} onClick={() => { setFilterDepartmentId(undefined); setFilterUnitId(unit.id); if (!scope.data.location_locked) setFilterLocationId(undefined); setPage(1); }}>{unit.name}</Button>)}
      </div>
      <Button variant="outline" onClick={() => setBulkImportOpen(true)}>Import Excel</Button>
      <PrintPreviewButton src={printSrc} title="Journal Register" ariaLabel="Preview journal register" label="Print" />
      <Button disabled={!scopeReady} onClick={openCreate}>+ New Journal</Button>
    </div>} />
    {scope.isError && <p role="alert" className="text-sm text-red-700">Journal location scope could not be loaded.</p>}
    <div className="grid grid-cols-2 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm xl:grid-cols-4" aria-label="Filtered journal totals">
      <div className="min-w-0 border-b border-r border-slate-100 px-3 py-2 xl:border-b-0"><div className="text-[11px] font-medium text-slate-500">Journal entries</div><div className="text-lg font-semibold tabular-nums leading-6 text-slate-900">{(q.data?.total_items ?? 0).toLocaleString("id-ID")}</div><div className="text-[10px] text-slate-500">Matching current filters</div></div>
      <div className="min-w-0 border-b border-slate-100 px-3 py-2 xl:border-b-0 xl:border-r"><div className="text-[11px] font-medium text-slate-500">Total debit</div><div className="truncate text-base font-semibold tabular-nums leading-6 text-slate-900" title={filteredJournalTotals ? formatAmount(filteredJournalTotals.debit) : undefined}>{filteredJournalTotals ? formatAmount(filteredJournalTotals.debit) : "—"}</div><div className="truncate text-[10px] tabular-nums text-slate-500" title={`This page: ${formatAmount(visibleTotals.debit)}`}>Page: {formatAmount(visibleTotals.debit)}</div></div>
      <div className="min-w-0 border-r border-slate-100 px-3 py-2"><div className="text-[11px] font-medium text-slate-500">Total credit</div><div className="truncate text-base font-semibold tabular-nums leading-6 text-slate-900" title={filteredJournalTotals ? formatAmount(filteredJournalTotals.credit) : undefined}>{filteredJournalTotals ? formatAmount(filteredJournalTotals.credit) : "—"}</div><div className="truncate text-[10px] tabular-nums text-slate-500" title={`This page: ${formatAmount(visibleTotals.credit)}`}>Page: {formatAmount(visibleTotals.credit)}</div></div>
      <div className={`min-w-0 px-3 py-2 ${hasDifference ? "bg-red-50/70" : "bg-emerald-50/30"}`}>
        <div className="flex items-center gap-1.5 text-[11px] font-medium text-slate-600">Debit − credit {hasDifference && <AlertTriangle className="text-red-600" size={13}/>}</div>
        <div className={`truncate text-base font-semibold tabular-nums leading-6 ${hasDifference ? "text-red-700" : "text-slate-900"}`} title={filteredDifference === null ? undefined : formatAmount(filteredDifference)}>{filteredDifference === null ? "—" : formatAmount(filteredDifference)}</div>
        {hasDifference ? <button type="button" className="text-[10px] font-semibold text-red-700 underline underline-offset-2 hover:text-red-900" onClick={() => { setBalanceState("UNBALANCED"); setShowFilters(true); setPage(1); }}>Review unbalanced journals</button> : <div className="text-[10px] text-slate-500">{filteredDifference === null ? "Totals unavailable" : "Balanced"}</div>}
      </div>
    </div>
    <Card className="workspace-data overflow-hidden p-0">
    <div className="workspace-toolbar flex flex-wrap items-end gap-3 border-b border-slate-100 pb-3">
      <label className="min-w-[210px] flex-[2] text-xs font-medium text-slate-600">Find a journal
        <input className="mt-1 h-9 w-full rounded-md border border-slate-300 bg-white px-3 outline-none focus:border-emerald-600" placeholder="Journal no., document, or description" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} />
      </label>
      <label className="min-w-[145px] flex-1 text-xs font-medium text-slate-600">Period
        <input type="month" aria-label="Journal period" className="mt-1 h-9 w-full rounded-md border border-slate-300 bg-white px-2 outline-none focus:border-emerald-600" value={selectedMonth} onChange={e => changeMonth(e.target.value)} />
      </label>
      <label className="min-w-[140px] flex-1 text-xs font-medium text-slate-600">Status
        <select className="mt-1 h-9 w-full rounded-md border border-slate-300 bg-white px-2" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}><option value="">All statuses</option><option value="DRAFT">Draft</option><option value="POSTED">Posted</option><option value="VOID">Void</option></select>
      </label>
      <label className="min-w-[150px] flex-1 text-xs font-medium text-slate-600">Source
        <select aria-label="Source type" className="mt-1 h-9 w-full rounded-md border border-slate-300 bg-white px-2" value={referenceType} onChange={e=>{setReferenceType(e.target.value);setPage(1);}}><option value="">All sources</option>{Array.from(new Set<string>([...(q.data?.reference_types??[]),...(referenceType?[referenceType]:[])])).map(value=><option key={value} value={value}>{value.replaceAll("_"," ")}</option>)}</select>
      </label>
      <Button type="button" size="sm" variant="outline" aria-expanded={showFilters} onClick={() => setShowFilters(value => !value)}>
        <SlidersHorizontal size={15}/> More filters{advancedFilterCount ? ` (${advancedFilterCount})` : ""}
      </Button>
      {(search || status || dateFrom || dateTo || referenceType || advancedFilterCount > 0) && <button type="button" className="h-9 text-xs font-medium text-slate-500 hover:text-slate-800 hover:underline" onClick={clearJournalFilters}>Clear filters</button>}
    </div>
    {(dateFrom || dateTo) && !selectedMonth && <p className="mb-2 text-xs text-slate-500">Custom date range: {dateFrom || "Any"} – {dateTo || "Any"}. Change it in More filters.</p>}
    {showFilters && <div className="mb-2 grid gap-2 border-t border-slate-100 pt-2 md:grid-cols-3">
      <label className="text-xs">From Date<input aria-label="From Date" className="mt-1 h-9 w-full rounded border px-2" type="date" value={dateFrom} onChange={e=>{setDateFrom(e.target.value);setPage(1);}}/></label>
      <label className="text-xs">To Date<input aria-label="To Date" className="mt-1 h-9 w-full rounded border px-2" type="date" value={dateTo} onChange={e=>{setDateTo(e.target.value);setPage(1);}}/></label>
      <label className="text-xs">Balance<select aria-label="Journal balance" className="mt-1 h-9 w-full rounded border px-2" value={balanceState} onChange={e=>{setBalanceState(e.target.value);setPage(1);}}><option value="ALL">All</option><option value="BALANCED">Balanced</option><option value="UNBALANCED">Unbalanced</option></select></label>
      <label className="text-xs">Difference amount<input aria-label="Difference amount" className="mt-1 h-9 w-full rounded border px-2 text-right" type="number" min="0" step="0.01" placeholder="Any difference" value={differenceAmount} onChange={e=>{setDifferenceAmount(e.target.value);setPage(1);}}/></label>
      <SearchableSelect label="Account" value={filterAccountId} placeholder="Account code or name..." options={(filterAccounts.data??[]).map(row=>({id:row.id,label:`${row.account_code} — ${row.account_name}`}))} onChange={id=>{setFilterAccountId(id);setPage(1);}}/>
      <SearchableSelect label="Department" value={filterDepartmentId} placeholder="Department name..." options={(filterDepartments.data??[]).map(row=>({id:row.id,label:row.name}))} onChange={id=>{setFilterDepartmentId(id);setPage(1);}}/>
      <SearchableSelect label="Location" value={filterLocationId} disabled={scope.isLoading || scope.data?.location_locked} placeholder={filterLocations.isLoading ? "Loading locations..." : "Type location code or name..."} options={filterLocationOptions} onChange={(id) => { setFilterLocationId(id); setFilterDepartmentId(undefined); setPage(1); }} />
      <SearchableSelect label="Supplier" value={filterSupplierId} disabled={filterSuppliers.isLoading} placeholder={filterSuppliers.isLoading ? "Loading suppliers..." : "Type supplier code or name..."} options={filterSupplierOptions} onChange={(id) => { setFilterSupplierId(id); setPage(1); }} />
    </div>}
      {canBulkManage && selectedRows.length > 0 && <div role="toolbar" aria-label="Selected journal actions" className="mb-2 flex flex-wrap items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs">
        <span className="mr-1 font-semibold text-emerald-900">{selectedRows.length} selected on this page</span>
        <Button size="sm" disabled={bulkLifecycle.isPending || bulkCandidates("post").length === 0} loading={bulkLifecycle.isPending} onClick={() => runBulk("post")}>Post selected ({bulkCandidates("post").length})</Button>
        <Button size="sm" variant="outline" disabled={bulkLifecycle.isPending || bulkCandidates("unpost").length === 0} loading={bulkLifecycle.isPending} onClick={() => runBulk("unpost")}>Unpost selected ({bulkCandidates("unpost").length})</Button>
        <button type="button" className="ml-auto font-medium text-emerald-800 hover:underline" onClick={() => setSelected([])}>Clear selection</button>
      </div>}
      <JournalRegisterTable
        rows={visibleRows} loading={q.isLoading} error={q.isError} selectedIds={selected}
        allPageSelected={allVisibleSelected} onTogglePage={toggleAllVisible}
        onToggleRow={(id) => setSelected(current => current.includes(id) ? current.filter(value => value !== id) : [...current, id])}
        onView={openJournal} onCopy={(id) => copy.mutate(id)}
        onPost={(id) => lifecycle.mutate({ id, action: "post" })}
        onUnpost={(id) => lifecycle.mutate({ id, action: "unpost" })}
        onVoidPayment={(row) => { if (window.confirm(`Void payment ${row.reference_number} and its draft journal ${row.journal_number}? This releases the invoice reservation and keeps both records as VOID.`)) voidSourcePayment.mutate(row.reference_id); }}
        actionPending={copy.isPending || lifecycle.isPending || voidSourcePayment.isPending}
      />
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-2 text-xs">
        <label>Rows per page <select className="ml-1 rounded border border-slate-300 bg-white px-2 py-1" value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }}><option value={50}>50</option><option value={100}>100</option></select></label>
        <div className="flex items-center gap-2"><span>{q.data?.total_items ?? 0} journals · Page {page} of {Math.max(q.data?.total_pages ?? 0, 1)}</span><Button size="sm" variant="outline" disabled={!q.data?.has_previous} onClick={() => setPage(page - 1)}>Previous</Button><Button size="sm" variant="outline" disabled={!q.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button></div>
      </div>
    </Card>

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

