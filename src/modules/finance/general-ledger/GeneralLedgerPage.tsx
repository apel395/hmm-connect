import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import PageHeader from "@/components/common/PageHeader";
import { Download } from "lucide-react";
import Button from "@/components/ui/Button";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Card from "@/components/ui/Card";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { TABLE_UI } from "@/config/tableUi";
import SearchableSelect from "@/components/form/SearchableSelect";
import { getAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { listLocations } from "@/modules/admin/organization/api";
import { createLedgerExport, getAccountSummary, getExport, listLedger } from "./api";

const amount = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID");
const EXPORT_POLL_DELAYS_MS = [2000, 3000, 5000, 8000, 10000];
const EXPORT_BACKGROUND_POLL_DELAY_MS = 15000;
const EXPORT_POLL_TIMEOUT_MS = 5 * 60 * 1000;

export default function GeneralLedgerPage() {
  const [searchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [filters, setFilters] = useState<any>({ search: searchParams.get("search") || "", account_id: searchParams.get("account_id") || "", date_from: searchParams.get("date_from") || "", date_to: searchParams.get("date_to") || "", reference_type: searchParams.get("reference_type") || "", supplier_id: searchParams.get("supplier_id") || "", department_id: searchParams.get("department_id") || "", location_id: searchParams.get("location_id") || "", business_unit_id: searchParams.get("business_unit_id") || "" });
  const [exportJobId, setExportJobId] = useState<string | null>(null);
  const [exportStatus, setExportStatus] = useState<"idle" | "starting" | "processing" | "failed">("idle");
  const [exportError, setExportError] = useState<string | null>(null);
  const params = Object.fromEntries(Object.entries({ ...filters, page, page_size: 20 }).filter(([, value]) => value !== ""));
  const ledger = useQuery({ queryKey: ["general-ledger", params], queryFn: () => listLedger(params) });
  const locations = useQuery({ queryKey: ["ledger-filter-locations", "active"], queryFn: () => listLocations({ is_active: true }) });
  const accounts = useQuery({ queryKey: ["ledger-accounts"], queryFn: () => getAccountLookup({ is_active: true }) });
  const summary = useQuery({ queryKey: ["ledger-summary", filters.account_id, filters.date_from, filters.date_to], queryFn: () => getAccountSummary(Number(filters.account_id), { date_from: filters.date_from || undefined, date_to: filters.date_to || undefined }), enabled: !!filters.account_id });
  const change = (key: string, value: string) => { setFilters({ ...filters, [key]: value }); setPage(1); };
  const input = "h-10 rounded border px-3";

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
  const printHeader = (() => {
    const parts: string[] = [];
    if (filters.date_from || filters.date_to) parts.push(`${filters.date_from || "…"} to ${filters.date_to || "…"}`);
    if (filters.account_id) {
      const account = accounts.data?.find((a: any) => String(a.id) === String(filters.account_id));
      if (account) parts.push(`${account.account_code} — ${account.account_name}`);
    }
    return parts.join(" · ");
  })();
  const exportLabel = exportStatus === "starting"
    ? "Starting export..."
    : exportStatus === "processing"
      ? "Preparing XLS..."
      : "Download XLS";

  return <div className="print-document space-y-6"><style>{`@page{size:landscape;margin:10mm}`}</style><div className="hidden print:block"><h1 className="text-2xl font-bold">MMH-Connect</h1><h2 className="text-xl font-semibold">General Ledger</h2><p className="text-xs text-slate-600">{printHeader}</p><p className="text-xs text-slate-500">Printed {new Date().toLocaleString()}</p></div>
    <div className="print:hidden space-y-6">
    <PageHeader actions={<div className="flex items-center gap-2">
    <Button onClick={handleExport} disabled={exportBusy}><Download size={16} /> {exportLabel}</Button>
    <PrintPreviewButton src={printSrc} title="General Ledger" ariaLabel="Preview general ledger" />
  </div>} title="General Ledger" description="Read-only posted journal activity with server-calculated balances."/>
    {exportError && <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{exportError}</div>}
    <Card><div className="grid gap-3 md:grid-cols-4"><input className={input} placeholder="Search journal, document, description" value={filters.search} onChange={event => change("search", event.target.value)}/><select className={input} value={filters.account_id} onChange={event => change("account_id", event.target.value)}><option value="">All accounts</option>{accounts.data?.map(account => <option key={account.id} value={account.id}>{account.account_code} — {account.account_name}</option>)}</select><input className={input} type="date" value={filters.date_from} onChange={event => change("date_from", event.target.value)}/><input className={input} type="date" value={filters.date_to} onChange={event => change("date_to", event.target.value)}/><select className={input} value={filters.reference_type} onChange={event => change("reference_type", event.target.value)}><option value="">All document types</option><option>SUPPLIER_INVOICE</option><option>SUPPLIER_PAYMENT</option><option>MANUAL</option></select><input className={input} placeholder="Supplier ID" value={filters.supplier_id} onChange={event => change("supplier_id", event.target.value)}/><input className={input} placeholder="Department ID" value={filters.department_id} onChange={event => change("department_id", event.target.value)}/><div><SearchableSelect label="Location" value={filters.location_id ? Number(filters.location_id) : undefined} disabled={locations.isLoading} placeholder={locations.isLoading ? "Loading locations..." : "Type location code or name..."} options={(locations.data ?? []).map((item: any) => ({ id: item.id, label: `${item.code} — ${item.name}`, keywords: [item.code ?? "", item.name ?? ""] }))} onChange={(id) => change("location_id", id ? String(id) : "")} /></div></div></Card>
    {summary.data && <Card><div className="grid gap-4 text-right md:grid-cols-4"><div><small>Opening Balance</small><div className="font-bold tabular-nums">{amount(summary.data.opening_balance)}</div></div><div><small>Total Debit</small><div className="font-bold tabular-nums">{amount(summary.data.total_debit)}</div></div><div><small>Total Credit</small><div className="font-bold tabular-nums">{amount(summary.data.total_credit)}</div></div><div><small>Closing Balance</small><div className="font-bold tabular-nums">{amount(summary.data.closing_balance)}</div></div></div></Card>}
    </div>
    <Card>
      <Table variant="grid" stickyHeader className="min-w-[980px]" containerClassName="border-0 shadow-none">
        <THead><TR className="whitespace-nowrap"><TH>Date</TH><TH>Journal</TH><TH>Account</TH><TH>Description</TH><TH>Document</TH><TH numeric>Debit</TH><TH numeric>Credit</TH><TH numeric>Balance</TH><TH>Context</TH></TR></THead>
        <TBody>{ledger.data?.items.map((row: any) => {
          const contextPrimary = row.supplier_name || row.business_unit_name;
          const contextSecondary = [row.department_name, row.location_name].filter(Boolean).join(" · ");
          return <TR key={row.id}>
            <TD className="whitespace-nowrap">{row.posting_date}</TD>
            <TD className="whitespace-nowrap"><Link className={TABLE_UI.documentLink} to={`/journal-entries/${row.journal_id}`}>{row.journal_number}</Link></TD>
            <TD className="max-w-[200px]"><TableCellStack primary={row.account_name} secondary={row.account_code}/></TD>
            <TD className="max-w-[220px]"><span className="block truncate" title={row.description || undefined}>{row.description || "—"}</span></TD>
            <TD className="max-w-[160px]"><span className="block truncate font-medium text-slate-700" title={row.reference_number || undefined}>{row.reference_number || "—"}</span></TD>
            <TD numeric className="whitespace-nowrap">{amount(row.debit)}</TD>
            <TD numeric className="whitespace-nowrap">{amount(row.credit)}</TD>
            <TD numeric className="whitespace-nowrap font-semibold">{amount(row.balance)}</TD>
            <TD className="max-w-[180px]">{contextPrimary || contextSecondary ? <TableCellStack primary={contextPrimary || contextSecondary} secondary={contextPrimary ? contextSecondary : undefined}/> : "—"}</TD>
          </TR>;
        })}</TBody>
      </Table>
      <div className="mt-4 flex justify-end gap-2 print:hidden"><Button variant="outline" disabled={!ledger.data?.has_previous} onClick={() => setPage(page - 1)}>Previous</Button><Button variant="outline" disabled={!ledger.data?.has_next} onClick={() => setPage(page + 1)}>Next</Button></div>
    </Card>
  </div>;
}
