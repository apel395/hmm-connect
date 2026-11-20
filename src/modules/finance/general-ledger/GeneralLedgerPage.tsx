import { unbalancedJournalPath } from "../journals/journalFilters";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import ReportUnitButtons from "@/components/reports/ReportUnitButtons";
import { useQuery } from "@tanstack/react-query";
import { Fragment, useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import { ChevronDown, ChevronRight, Download, Layers3, List, Rows3, SlidersHorizontal } from "lucide-react";
import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Card from "@/components/ui/Card";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { TABLE_UI } from "@/config/tableUi";
import SearchableSelect from "@/components/form/SearchableSelect";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { listDepartments, listLocations } from "@/modules/admin/organization/api";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import { createLedgerExport, getAccountSummary, getExport, getLedgerAccountBalances, listLedger } from "./api";
import type { LedgerAccountBalance } from "./api";

const amount = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const EXPORT_POLL_DELAYS_MS = [2000, 3000, 5000, 8000, 10000];
const EXPORT_BACKGROUND_POLL_DELAY_MS = 15000;
const EXPORT_POLL_TIMEOUT_MS = 5 * 60 * 1000;

export default function GeneralLedgerPage() {
  const [searchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => Number(window.localStorage.getItem("ledger-page-size")) === 100 ? 100 : 50);
  const [showFilters, setShowFilters] = useState(false);
  const [showDisplayTools, setShowDisplayTools] = useState(false);
  const [denseRows, setDenseRows] = useState(() => window.localStorage.getItem("gl-row-density") !== "comfortable");
  const [groupByAccount, setGroupByAccount] = useState(true);
  const [collapsedAccounts, setCollapsedAccounts] = useState<number[]>([]);
  const [filters, setFilters] = useState<any>({ account_ids: searchParams.get("account_ids") || "", search: searchParams.get("search") || "", search_type: searchParams.get("search_type") || "ALL", account_id: searchParams.get("account_id") || "", account_from_id: searchParams.get("account_from_id") || "", account_to_id: searchParams.get("account_to_id") || "", date_from: searchParams.get("date_from") ?? `${new Date().getFullYear()}-01-01`, date_to: searchParams.get("date_to") || "", reference_type: searchParams.get("reference_type") || "", supplier_id: searchParams.get("supplier_id") || "", department_id: searchParams.get("department_id") || "", location_id: searchParams.get("location_id") || "", business_unit_id: searchParams.get("business_unit_id") || "" });
  const [exportJobId, setExportJobId] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState<"idle" | "starting" | "processing" | "failed">("idle");
  const [exportError, setExportError] = useState<string | null>(null);
  const params = Object.fromEntries(Object.entries({ ...filters, page, page_size: pageSize }).filter(([, value]) => value !== ""));
  const ledger = useQuery({ queryKey: ["general-ledger", params], queryFn: () => listLedger(params) });
  const locations = useQuery({ queryKey: ["ledger-filter-locations", filters.business_unit_id], queryFn: () => listLocations({ is_active: true, business_unit_id:Number(filters.business_unit_id)||undefined }) });
  const departments = useQuery({ queryKey: ["ledger-filter-departments", filters.business_unit_id], queryFn: () => listDepartments({ is_active: true, business_unit_id: Number(filters.business_unit_id) || undefined }) });
  const suppliers = useSuppliers("", 100, showFilters);
  const accounts = useQuery({ queryKey: ["ledger-accounts", "all"], queryFn: () => getAllAccountLookup() });
  const summary = useQuery({ queryKey: ["ledger-summary", filters.account_id, filters.date_from, filters.date_to, filters.business_unit_id, filters.location_id, filters.department_id], queryFn: () => getAccountSummary(Number(filters.account_id), { business_unit_id:Number(filters.business_unit_id)||undefined, location_id:Number(filters.location_id)||undefined, department_id:Number(filters.department_id)||undefined, date_from: filters.date_from || undefined, date_to: filters.date_to || undefined }), enabled: !!filters.account_id });
  const change = (key: string, value: string) => { setFilters({ ...filters, [key]: value }); setPage(1); };
  useEffect(() => window.localStorage.setItem("ledger-page-size", String(pageSize)), [pageSize]);
  useEffect(() => window.localStorage.setItem("gl-row-density", denseRows ? "dense" : "comfortable"), [denseRows]);
  const input = "h-8 rounded border border-slate-300 bg-white px-2 text-xs";
  const activeAdvancedFilters = ["search_type","account_id","account_ids","account_from_id","account_to_id","reference_type","supplier_id","department_id","location_id"].filter(key => filters[key] && (key !== "search_type" || filters[key] !== "ALL")).length;

  useEffect(() => {
    if (!exportJobId) return;

    let cancelled = false;
    let timer: number | undefined;
    let pollAttempt = 0;
    const startedAt = Date.now();

    const scheduleNextPoll = (poll: () => Promise<void>) => {
      if (cancelled) return;
      const foregroundDelay = EXPORT_POLL_DELAYS_MS[Math.min(pollAttempt, EXPORT_POLL_DELAYS_MS.length - 1)];
      const delay = document.visibilityState === "hidden"
        ? EXPORT_BACKGROUND_POLL_DELAY_MS
        : foregroundDelay;
      pollAttempt += 1;
      timer = window.setTimeout(poll, delay);
    };

    const poll = async () => {
      if (cancelled) return;
      if (Date.now() - startedAt >= EXPORT_POLL_TIMEOUT_MS) {
        setExportStatus("failed");
        setExportJobId(null);
        setExportError("Export is taking longer than expected. Please try again later.");
        return;
      }
      try {
        const job = await getExport(exportJobId);
        if (cancelled) return;
        if (job.status === "READY" && job.download_url) {
          setExportStatus("idle");
          setExportJobId(null);
          setExportError(null);
          window.location.assign(job.download_url);
          return;
        }
        if (job.status === "FAILED") {
          setExportStatus("failed");
          setExportJobId(null);
          setExportError(job.error_message || "Export failed");
          return;
        }
        setExportStatus("processing");
        scheduleNextPoll(poll);
      } catch (error: any) {
        if (cancelled) return;
        setExportStatus("failed");
        setExportJobId(null);
        setExportError(error?.response?.data?.detail || "Unable to check export status");
      }
    };

    scheduleNextPoll(poll);
    return () => {
      cancelled = true;
      if (timer) window.clearTimeout(timer);
    };
  }, [exportJobId]);

  const printParams = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ""));
  const printQuery = new URLSearchParams(printParams as Record<string, string>).toString();
  const printSrc = `/general-ledger/print${printQuery ? `?${printQuery}` : ""}`;

  const handleExport = async () => {
    setExportError(null);
    setExportStatus("starting");
    try {
      const job = await createLedgerExport(printParams);
      setExportJobId(job.job_id);
      setExportStatus("processing");
    } catch (error: any) {
      setExportStatus("failed");
      setExportError(error?.response?.data?.detail || "Unable to start export");
    }
  };

  const exportBusy = exportStatus === "starting" || exportStatus === "processing";
  const pageTotals = (ledger.data?.items ?? []).reduce((sum: { debit: number; credit: number }, row: any) => ({
    debit: sum.debit + Number(row.debit || 0),
    credit: sum.credit + Number(row.credit || 0),
  }), { debit: 0, credit: 0 });
  // This grouping uses the current API page; page subtotals are not account closing balances.
  type AccountGroup = { id: number; code: string; name: string; rows: any[]; debit: number; credit: number };
  const accountGroups = Array.from<AccountGroup>(
    (ledger.data?.items ?? []).reduce((groups: Map<number, AccountGroup>, row: any) => {
      const id = Number(row.account_id);
      if (!groups.has(id)) groups.set(id, { id, code: row.account_code || "—", name: row.account_name || "Unknown account", rows: [], debit: 0, credit: 0 });
      const group = groups.get(id)!;
      group.rows.push(row);
      group.debit += Number(row.debit || 0);
      group.credit += Number(row.credit || 0);
      return groups;
    }, new Map<number, AccountGroup>()).values(),
  ).sort((a, b) => a.code.localeCompare(b.code, undefined, { numeric: true }));
  const accountGroupIds = accountGroups.map(group => group.id).join(",");
  const accountBalances = useQuery({
    queryKey: ["gl-account-balances", accountGroupIds, filters.date_from, filters.date_to, filters.business_unit_id, filters.location_id, filters.department_id],
    queryFn: () => getLedgerAccountBalances({
      account_ids: accountGroupIds,
      date_from: filters.date_from || undefined,
      date_to: filters.date_to || undefined,
      business_unit_id: filters.business_unit_id || undefined,
      location_id: filters.location_id || undefined,
      department_id: filters.department_id || undefined,
    }),
    enabled: groupByAccount && Boolean(accountGroupIds),
  });
  const accountBalanceById = new Map<number, LedgerAccountBalance>((accountBalances.data?.items ?? []).map(row => [row.account_id, row]));
  const balanceIsFiltered = Boolean(filters.search || filters.reference_type || filters.supplier_id);
  const toggleAccount = (id: number) => setCollapsedAccounts(previous => previous.includes(id) ? previous.filter(value => value !== id) : [...previous, id]);
  const summaryAvailable = ledger.data?.summary?.total_debit != null && ledger.data?.summary?.total_credit != null;
  const filteredTotals = summaryAvailable ? {
    debit: Number(ledger.data.summary.total_debit),
    credit: Number(ledger.data.summary.total_credit),
  } : null;
  const printHeader = (() => {
    const parts: string[] = [];
    if (filters.date_from || filters.date_to) parts.push(`${filters.date_from || "…"} to ${filters.date_to || "…"}`);
    if (filters.account_id) {
      const account = accounts.data?.find((a: any) => String(a.id) === String(filters.account_id));
      if (account) parts.push(account.account_name);
    }
    return parts.join(" · ");
  })();
  const documentLink = (row: any): string | null => {
    const id = Number(row.reference_id);
    if (!Number.isSafeInteger(id) || id <= 0) return null;
    const paths: Record<string, string> = {
      GOODS_RECEIPT: "/receiving",
      SUPPLIER_INVOICE: "/supplier-invoices",
      SUPPLIER_PAYMENT: "/payments",
      BANK_TRANSFER: "/bank-transfers",
    };
    const base = paths[String(row.reference_type ?? "").toUpperCase()];
    return base ? `${base}/${id}` : null;
  };
  const renderLedgerRow = (row: any) => {
    const contextPrimary = row.supplier_name || row.business_unit_name;
    const contextSecondary = [row.department_name, row.location_name].filter(Boolean).join(" · ");
    return <TR key={row.id}>
      <TD className="whitespace-nowrap">{row.posting_date}</TD>
      <TD className="whitespace-nowrap"><Link className={TABLE_UI.documentLink} to={`/journal-entries/${row.journal_id}`}>{row.journal_number}</Link></TD>
      <TD className="max-w-[200px]"><span className="block truncate" title={`${row.account_code} — ${row.account_name}`}>{row.account_name}</span></TD>
      <TD className="max-w-[220px]"><span className="block truncate" title={row.description || undefined}>{row.description || "—"}</span></TD>
      <TD className="max-w-[160px]">{documentLink(row) ? <Link className={TABLE_UI.documentLink} to={documentLink(row)!} title={row.reference_number || "Open source document"}>{row.reference_number || row.reference_type || "Open source"}</Link> : <span className="block truncate font-medium text-slate-700" title={row.reference_number || undefined}>{row.reference_number || "—"}</span>}</TD>
      <TD numeric className="whitespace-nowrap">{amount(row.debit)}</TD>
      <TD numeric className="whitespace-nowrap">{amount(row.credit)}</TD>
      <TD numeric className="whitespace-nowrap font-semibold">{amount(row.balance)}</TD>
      <TD className="max-w-[180px]">{contextPrimary || contextSecondary ? <TableCellStack primary={contextPrimary || contextSecondary} secondary={contextPrimary ? contextSecondary : undefined}/> : "—"}</TD>
    </TR>;
  };
  const exportLabel = exportStatus === "starting"
    ? "Starting export..."
    : exportStatus === "processing"
      ? "Preparing XLS..."
      : "Download XLS";

  return <DataWorkspace area="Accounting" className="print-document "><style>{`@page{size:landscape;margin:10mm}
    .gl-compact-ledger tbody tr td { padding: 2px 7px; font-size: 12px; line-height: 16px; }
    .gl-compact-ledger thead tr th { height: 27px; padding: 4px 7px; }
    .gl-compact-ledger tbody tr button { line-height: 16px; }
    @media print { .gl-compact-ledger tbody tr td { padding: 4px 7px; font-size: 11px; } }
  `}</style><div className="hidden print:block"><h1 className="text-2xl font-bold">MMH-Connect</h1><h2 className="text-xl font-semibold">General Ledger</h2><p className="text-xs text-slate-600">{printHeader}</p><p className="text-xs text-slate-500">Printed {new Date().toLocaleString()}</p></div>
    <div className="print:hidden space-y-2">
    <PageHeader actions={<div className="flex items-center gap-2">
    <Button size="sm" variant="outline" title={exportLabel} aria-label={exportLabel} onClick={handleExport} disabled={exportBusy}><Download size={15} />{exportBusy && <span>{exportLabel}</span>}</Button>
    <PrintPreviewButton src={printSrc} title="General Ledger" ariaLabel="Preview general ledger" />
  </div>} title="General Ledger"/>
    <ReportUnitButtons value={filters.business_unit_id} onChange={id=>{setFilters({...filters,business_unit_id:id,location_id:"",department_id:""});setPage(1);}}/>
    {exportError && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{exportError}</div>}
    <Card className="workspace-filter-panel p-2">
      <div className="flex flex-wrap items-end gap-2">
        <label className="min-w-[220px] flex-[2_1_320px] text-xs font-medium text-slate-700">Search
          <input className={`${input} mt-0.5 w-full`} placeholder="Journal, document, description, account..." value={filters.search} onChange={event => change("search", event.target.value)}/>
        </label>
        <label className="min-w-[145px] flex-1 text-xs font-medium text-slate-700">From Date
          <input className={`${input} mt-0.5 w-full`} type="date" value={filters.date_from} onChange={event => change("date_from", event.target.value)}/>
        </label>
        <label className="min-w-[145px] flex-1 text-xs font-medium text-slate-700">To Date
          <input className={`${input} mt-0.5 w-full`} type="date" value={filters.date_to} onChange={event => change("date_to", event.target.value)}/>
        </label>
        <Button type="button" size="sm" variant="outline" title="Open transaction filters" aria-label="Open General Ledger filters" aria-expanded={showFilters} onClick={() => setShowFilters(true)}><SlidersHorizontal size={15}/><span className="sr-only">Filters</span>{activeAdvancedFilters ? <span className="text-xs">{activeAdvancedFilters}</span> : null}</Button>
        <Button type="button" size="sm" variant="outline" title="Display preferences" aria-label="Ledger display preferences" onClick={() => setShowDisplayTools(true)}><Rows3 size={15}/><span className="sr-only">Display</span></Button>
      </div>
    </Card>
    <Dialog open={showFilters} onOpenChange={setShowFilters}>
      <DialogContent className="max-w-3xl">
        <DialogHeader><DialogTitle>General Ledger filters</DialogTitle></DialogHeader>
        <DialogBody>
          <p className="mb-3 text-xs text-slate-500">Refine the displayed transactions. Dates and business unit remain available on the main screen.</p>
          <div className="space-y-3">

        <div className="grid gap-2 md:grid-cols-3">
          <label className="text-xs">Search Type
            <select className={`${input} mt-0.5 w-full`} value={filters.search_type} onChange={event=>change("search_type",event.target.value)}>
              <option value="ALL">All fields</option><option value="JOURNAL">Journal No.</option><option value="DOCUMENT">Document No.</option><option value="DESCRIPTION">Description</option><option value="ACCOUNT">Account</option><option value="SUPPLIER">Supplier</option>
            </select>
          </label>
          <SearchableSelect maxOptions={Number.POSITIVE_INFINITY} label="Single Account" value={filters.account_id ? Number(filters.account_id) : undefined} disabled={accounts.isLoading} placeholder="Exact account..." options={(accounts.data ?? []).map((account: any) => ({ id: account.id, label: `${account.account_code} — ${account.account_name}${account.is_active ? "" : " (Inactive)"}`, keywords: [account.account_code ?? "", account.account_name ?? ""] }))} onChange={(id) => change("account_id", id ? String(id) : "")} />
          <select className={input} aria-label="Document type" value={filters.reference_type} onChange={event => change("reference_type", event.target.value)}><option value="">All document types</option><option>SUPPLIER_INVOICE</option><option>SUPPLIER_PAYMENT</option><option>MANUAL</option></select>
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          <SearchableSelect maxOptions={Number.POSITIVE_INFINITY} label="From Account" value={filters.account_from_id ? Number(filters.account_from_id) : undefined} disabled={accounts.isLoading || Boolean(filters.account_id)} placeholder="Start account..." options={(accounts.data ?? []).map((account: any) => ({ id: account.id, label: `${account.account_code} — ${account.account_name}${account.is_active ? "" : " (Inactive)"}`, keywords: [account.account_code ?? "", account.account_name ?? ""] }))} onChange={(id) => change("account_from_id", id ? String(id) : "")} />
          <SearchableSelect maxOptions={Number.POSITIVE_INFINITY} label="To Account" value={filters.account_to_id ? Number(filters.account_to_id) : undefined} disabled={accounts.isLoading || Boolean(filters.account_id)} placeholder="End account..." options={(accounts.data ?? []).map((account: any) => ({ id: account.id, label: `${account.account_code} — ${account.account_name}${account.is_active ? "" : " (Inactive)"}`, keywords: [account.account_code ?? "", account.account_name ?? ""] }))} onChange={(id) => change("account_to_id", id ? String(id) : "")} />
        </div>
        <div className="grid gap-2 md:grid-cols-3">
          <SearchableSelect label="Supplier" value={filters.supplier_id ? Number(filters.supplier_id) : undefined} disabled={suppliers.isLoading} placeholder="Select supplier..." options={(suppliers.data ?? []).map(item => ({ id: item.id, label: `${item.code} — ${item.name}`, keywords: [item.code, item.name] }))} onChange={id => change("supplier_id", id ? String(id) : "")}/>
          <SearchableSelect label="Department" value={filters.department_id ? Number(filters.department_id) : undefined} disabled={departments.isLoading} placeholder="Select department..." options={(departments.data ?? []).map(item => ({ id: item.id, label: `${item.code} — ${item.name}`, keywords: [item.code, item.name] }))} onChange={id => change("department_id", id ? String(id) : "")}/>
          <SearchableSelect label="Location" value={filters.location_id ? Number(filters.location_id) : undefined} disabled={locations.isLoading} placeholder={locations.isLoading ? "Loading locations..." : "Type location code or name..."} options={(locations.data ?? []).map((item: any) => ({ id: item.id, label: `${item.code} — ${item.name}`, keywords: [item.code ?? "", item.name ?? ""] }))} onChange={(id) => change("location_id", id ? String(id) : "")} />
        </div>

          </div>
        </DialogBody>
        <DialogFooter><div className="flex w-full items-center justify-between gap-2">
          <button type="button" className="rounded border border-slate-200 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50" onClick={() => {
            setFilters((current: any) => ({...current, search_type: "ALL", account_id: "", account_ids: "", account_from_id: "", account_to_id: "", reference_type: "", supplier_id: "", department_id: "", location_id: ""}));
            setPage(1);
          }}>Clear advanced filters</button>
          <Button type="button" size="sm" onClick={() => setShowFilters(false)}>Show results</Button>
        </div></DialogFooter>
      </DialogContent>
    </Dialog>
    <Dialog open={showDisplayTools} onOpenChange={setShowDisplayTools}>
      <DialogContent className="max-w-sm">
        <DialogHeader><DialogTitle>Ledger display</DialogTitle></DialogHeader>
        <DialogBody>
          <p className="mb-3 text-xs text-slate-500">Choose how many transaction rows fit on your screen.</p>
          <fieldset className="space-y-2">
            <legend className="mb-2 text-xs font-semibold text-slate-700">Row spacing</legend>
            <label className="flex cursor-pointer items-center gap-2 rounded border border-slate-200 p-2 text-sm">
              <input type="radio" name="gl-density" checked={denseRows} onChange={() => setDenseRows(true)}/> Dense — more entries visible
            </label>
            <label className="flex cursor-pointer items-center gap-2 rounded border border-slate-200 p-2 text-sm">
              <input type="radio" name="gl-density" checked={!denseRows} onChange={() => setDenseRows(false)}/> Comfortable — more spacing
            </label>
          </fieldset>
        </DialogBody>
        <DialogFooter><Button size="sm" onClick={() => setShowDisplayTools(false)}>Done</Button></DialogFooter>
      </DialogContent>
    </Dialog>
    <Card className="workspace-summary px-2 py-1"><div className="workspace-summary-fields"><div><small>Filtered Entries</small><div className="font-bold tabular-nums">{ledger.data?.total_items ?? 0}</div></div><div><small>Filtered Debit</small><div className="font-bold tabular-nums">{filteredTotals ? amount(filteredTotals.debit) : "Awaiting backend totals"}</div><small>Page: {amount(pageTotals.debit)}</small></div><div><small>Filtered Credit</small><div className="font-bold tabular-nums">{filteredTotals ? amount(filteredTotals.credit) : "Awaiting backend totals"}</div><small>Page: {amount(pageTotals.credit)}</small></div><div><small>Difference</small><div className="font-bold tabular-nums">{filteredTotals ? <Link to={unbalancedJournalPath(filters)} title="Find unbalanced posted journals in this period and scope" className="text-emerald-700 hover:underline">{amount(filteredTotals.debit-filteredTotals.credit)}</Link> : "Awaiting backend totals"}</div><small>Page: {amount(pageTotals.debit-pageTotals.credit)}</small></div></div></Card>
    {summary.data && <Card className="workspace-summary px-2 py-1"><div className="workspace-summary-fields"><div><small>Opening Balance</small><div className="font-bold tabular-nums">{amount(summary.data.opening_balance)}</div></div><div><small>Account Debit</small><div className="font-bold tabular-nums">{amount(summary.data.total_debit)}</div></div><div><small>Account Credit</small><div className="font-bold tabular-nums">{amount(summary.data.total_credit)}</div></div><div><small>Closing Balance</small><div className="font-bold tabular-nums">{amount(summary.data.closing_balance)}</div></div></div></Card>}
    </div>
    <div className="flex flex-wrap items-center justify-between gap-2 print:hidden">
      <div className="flex items-center gap-2 text-xs text-slate-600">
        <span>{ledger.data?.total_items ?? 0} matching entries</span>
        {balanceIsFiltered && <span className="rounded border border-amber-200 bg-amber-50 px-2 py-1 text-amber-900">Running balances include complete account movements; debit/credit search totals cover matching entries only.</span>}
      </div>
      <div className="inline-flex items-center gap-1 rounded-md border border-slate-200 p-1" role="group" aria-label="Ledger display mode">
        <button type="button" onClick={() => setGroupByAccount(true)} aria-pressed={groupByAccount} className={`flex items-center gap-1 rounded px-2 py-1 text-xs ${groupByAccount ? "bg-slate-800 text-white" : "text-slate-600 hover:bg-slate-100"}`}><Layers3 size={14}/> By account</button>
        <button type="button" onClick={() => setGroupByAccount(false)} aria-pressed={!groupByAccount} className={`flex items-center gap-1 rounded px-2 py-1 text-xs ${!groupByAccount ? "bg-slate-800 text-white" : "text-slate-600 hover:bg-slate-100"}`}><List size={14}/> Transactions</button>
      </div>
    </div>
    <Card className="workspace-data">
      <Table variant="grid" stickyHeader className={`workspace-ledger-table min-w-[980px] ${denseRows ? "gl-compact-ledger" : ""}`} containerClassName="min-h-[min(54vh,520px)] max-h-[calc(100dvh-300px)] overflow-auto border-0 shadow-none print:max-h-none print:min-h-0 print:overflow-visible">
        <THead><TR className="whitespace-nowrap"><TH>Date</TH><TH>Journal</TH><TH>Account</TH><TH>Description</TH><TH>Document</TH><TH numeric>Debit</TH><TH numeric>Credit</TH><TH numeric>Balance</TH><TH>Context</TH></TR></THead>
        <TBody>
          {ledger.isLoading && <TR><TD colSpan={9} className="py-10 text-center text-slate-500">Loading ledger…</TD></TR>}
          {ledger.isError && <TR><TD colSpan={9} className="py-10 text-center text-red-700">Ledger could not be loaded. Use Refresh to try again.</TD></TR>}
          {!ledger.isLoading && !ledger.isError && !ledger.data?.items.length && <TR><TD colSpan={9} className="py-10 text-center text-slate-500">No entries match these filters.</TD></TR>}
          {!groupByAccount && (ledger.data?.items ?? []).map(renderLedgerRow)}
          {groupByAccount && accountGroups.map(group => {
            const collapsed = collapsedAccounts.includes(group.id);
            return <Fragment key={group.id}>
              <TR className="bg-slate-100/80">
                <TD colSpan={9} className="px-3 py-2">
                  <button type="button" onClick={() => toggleAccount(group.id)} aria-expanded={!collapsed} className="flex w-full flex-wrap items-center justify-between gap-2 text-left text-sm font-semibold text-slate-800">
                    <span className="inline-flex items-center gap-2">{collapsed ? <ChevronRight size={16}/> : <ChevronDown size={16}/>}<span className="font-mono">{group.code}</span> — {group.name}</span>
                    <span className="text-xs font-normal text-slate-600">{group.rows.length} entries on this page</span>
                  </button>
                </TD>
              </TR>
              {!collapsed && <TR className="bg-slate-50 text-xs text-slate-700">
                <TD colSpan={9}>
                  {accountBalanceById.get(group.id) ? <span className="flex flex-wrap gap-x-5 gap-y-1">
                    <span>Opening: <strong>{amount(accountBalanceById.get(group.id)!.opening_balance)}</strong></span>
                    <span>Period debit: <strong>{amount(accountBalanceById.get(group.id)!.total_debit)}</strong></span>
                    <span>Period credit: <strong>{amount(accountBalanceById.get(group.id)!.total_credit)}</strong></span>
                    <span>Closing: <strong>{amount(accountBalanceById.get(group.id)!.closing_balance)}</strong></span>
                  </span> : <span>{accountBalances.isLoading ? "Loading full account balances..." : "Full account balances unavailable"}</span>}
                </TD>
              </TR>}
              {!collapsed && group.rows.map(renderLedgerRow)}
              {!collapsed && <TR className="bg-slate-50 font-medium text-slate-700">
                <TD colSpan={5} className="text-right text-xs">Page subtotal — {group.code} (not full account closing)</TD>
                <TD numeric className="whitespace-nowrap">{amount(group.debit)}</TD>
                <TD numeric className="whitespace-nowrap">{amount(group.credit)}</TD>
                <TD colSpan={2} className="text-xs text-slate-500">Closing: {accountBalanceById.get(group.id) ? amount(accountBalanceById.get(group.id)!.closing_balance) : "—"}</TD>
              </TR>}
            </Fragment>;
          })}
        </TBody>
      </Table>
      <div className="mt-1 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-1 text-xs print:hidden"><label>Rows per page <select className="ml-1 rounded border border-slate-300 bg-white px-2 py-1" value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }}><option value={50}>50</option><option value={100}>100</option></select></label><div className="flex items-center gap-2"><span>{ledger.data?.total_items ?? 0} entries · Page {page} of {Math.max(ledger.data?.total_pages ?? 0, 1)}</span><Button size="sm" variant="outline" disabled={!ledger.data?.has_previous} onClick={() => setPage(page - 1)}>Previous</Button><Button size="sm" variant="outline" disabled={!ledger.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button></div></div>
    </Card>
  </DataWorkspace>;
}

