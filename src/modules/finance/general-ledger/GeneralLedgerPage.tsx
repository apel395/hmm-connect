import { unbalancedJournalPath } from "../journals/journalFilters";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useVirtualizer } from "@tanstack/react-virtual";
import { todayLocal } from "@/utils/dateConstraints";
import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ChevronDown, ChevronRight, Info, Layers3, List, RotateCw, Rows3, SlidersHorizontal, X } from "lucide-react";
import { ExportButton } from "@/components/common/ReportActions";
import ModuleSummary, { type SummaryMetric } from "@/components/common/ModuleSummary";
import PageHeader from "@/components/common/PageHeader";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Card from "@/components/ui/Card";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import { TABLE_UI } from "@/config/tableUi";
import { apiErrorMessage } from "@/utils/apiError";
import SearchableSelect from "@/components/form/SearchableSelect";
import { getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import { listBusinessUnits, listDepartments, listLocations } from "@/modules/admin/organization/api";
import { useSuppliers } from "@/modules/master/suppliers/hooks/useSuppliers";
import { getAccountSummary, getLedgerAccountBalances, getLedgerPrint, listLedger } from "./api";
import { downloadGeneralLedgerReport } from "./export";
import type { LedgerAccountBalance } from "./api";

const amount = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

const SKELETON_WIDTHS = ["w-16", "w-24", "w-32", "w-40", "w-24", "w-20", "w-20", "w-20", "w-24"];

function GlTableSkeleton() {
  return <>{SKELETON_WIDTHS.slice(0, 8).map((_, rowIndex) => <TR key={`gl-skeleton-${rowIndex}`} className="gl-skeleton-row">
    {SKELETON_WIDTHS.map((width, cellIndex) => <TD key={cellIndex}>
      <span className={`block h-3 animate-pulse rounded bg-slate-200 ${width}`} />
    </TD>)}
  </TR>)}</>;
}

const glToday = todayLocal();
const glMonthStart = `${glToday.slice(0, 7)}-01`;

export default function GeneralLedgerPage() {
  const [searchParams] = useSearchParams();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(() => Number(window.localStorage.getItem("ledger-page-size")) === 100 ? 100 : 50);
  const [showFilters, setShowFilters] = useState(false);
  const [showDisplayTools, setShowDisplayTools] = useState(false);
  const [denseRows, setDenseRows] = useState(() => window.localStorage.getItem("gl-row-density") !== "comfortable");
  const [groupByAccount, setGroupByAccount] = useState(true);
  const [collapsedAccounts, setCollapsedAccounts] = useState<number[]>([]);
  const [filters, setFilters] = useState<any>({ account_ids: searchParams.get("account_ids") || "", search: searchParams.get("search") || "", search_type: searchParams.get("search_type") || "ALL", account_id: searchParams.get("account_id") || "", account_from_id: searchParams.get("account_from_id") || "", account_to_id: searchParams.get("account_to_id") || "", date_from: searchParams.get("date_from") ?? glMonthStart, date_to: searchParams.get("date_to") ?? glToday, reference_type: searchParams.get("reference_type") || "", supplier_id: searchParams.get("supplier_id") || "", department_id: searchParams.get("department_id") || "", location_id: searchParams.get("location_id") || "", business_unit_id: searchParams.get("business_unit_id") || "" });
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const params = Object.fromEntries(Object.entries({ ...filters, page, page_size: pageSize }).filter(([, value]) => value !== ""));
  const ledger = useQuery({ queryKey: ["general-ledger", params], queryFn: () => listLedger(params) });
  const businessUnits = useQuery({ queryKey: ["report-units"], queryFn: listBusinessUnits });
  const locations = useQuery({ queryKey: ["ledger-filter-locations", filters.business_unit_id], queryFn: () => listLocations({ is_active: true, business_unit_id:Number(filters.business_unit_id)||undefined }) });
  const departments = useQuery({ queryKey: ["ledger-filter-departments", filters.business_unit_id], queryFn: () => listDepartments({ is_active: true, business_unit_id: Number(filters.business_unit_id) || undefined }) });
  const suppliers = useSuppliers("", 100, showFilters);
  const accounts = useQuery({ queryKey: ["ledger-accounts", "all"], queryFn: () => getAllAccountLookup() });
  const summary = useQuery({ queryKey: ["ledger-summary", filters.account_id, filters.date_from, filters.date_to, filters.business_unit_id, filters.location_id, filters.department_id], queryFn: () => getAccountSummary(Number(filters.account_id), { business_unit_id:Number(filters.business_unit_id)||undefined, location_id:Number(filters.location_id)||undefined, department_id:Number(filters.department_id)||undefined, date_from: filters.date_from || undefined, date_to: filters.date_to || undefined }), enabled: !!filters.account_id });
  const change = (key: string, value: string) => { setFilters({ ...filters, [key]: value }); setPage(1); };
  useEffect(() => {
    const units = businessUnits.data;
    if (units?.length === 1 && !filters.business_unit_id) {
      setFilters((current: any) => ({ ...current, business_unit_id: String(units[0].id), location_id: "", department_id: "" }));
    }
  }, [businessUnits.data, filters.business_unit_id]);
  useEffect(() => window.localStorage.setItem("ledger-page-size", String(pageSize)), [pageSize]);
  useEffect(() => window.localStorage.setItem("gl-row-density", denseRows ? "dense" : "comfortable"), [denseRows]);
  const input = "h-9 rounded border border-slate-300 bg-white px-2 text-[13px] leading-5";
  const activeAdvancedFilters = ["search_type","account_id","account_ids","account_from_id","account_to_id","reference_type","supplier_id","department_id","location_id"].filter(key => filters[key] && (key !== "search_type" || filters[key] !== "ALL")).length;
  const lookupLabel = (rows: any[] | undefined, id: string, fallback: string) => {
    const match = rows?.find(row => String(row.id) === String(id));
    return match ? `${match.code ?? match.account_code ?? ""} — ${match.name ?? match.account_name ?? ""}`.replace(/^ — /, "") : fallback;
  };
  const activeChips = [
    { key: "search", label: "Search", value: filters.search },
    { key: "account_id", label: "Account", value: filters.account_id ? lookupLabel(accounts.data, filters.account_id, `Account #${filters.account_id}`) : "" },
    { key: "account_ids", label: "Accounts", value: filters.account_ids },
    { key: "account_from_id", label: "From account", value: filters.account_from_id ? lookupLabel(accounts.data, filters.account_from_id, `Account #${filters.account_from_id}`) : "" },
    { key: "account_to_id", label: "To account", value: filters.account_to_id ? lookupLabel(accounts.data, filters.account_to_id, `Account #${filters.account_to_id}`) : "" },
    { key: "reference_type", label: "Document", value: filters.reference_type },
    { key: "supplier_id", label: "Supplier", value: filters.supplier_id ? lookupLabel(suppliers.data as any[] | undefined, filters.supplier_id, `Supplier #${filters.supplier_id}`) : "" },
    { key: "department_id", label: "Department", value: filters.department_id ? lookupLabel(departments.data as any[] | undefined, filters.department_id, `Department #${filters.department_id}`) : "" },
    { key: "location_id", label: "Location", value: filters.location_id ? lookupLabel(locations.data as any[] | undefined, filters.location_id, `Location #${filters.location_id}`) : "" },
  ].filter(chip => Boolean(chip.value));
  const clearAllChips = () => {
    setFilters((current: any) => ({ ...current, search: "", account_id: "", account_ids: "", account_from_id: "", account_to_id: "", reference_type: "", supplier_id: "", department_id: "", location_id: "" }));
    setPage(1);
  };

  const printParams = Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== ""));
  // Grouped view needs every entry for each account, not one globally paginated slice.
  // The report endpoint already returns the complete account-grouped ledger with
  // matching opening/movement/closing values, so reuse it instead of grouping a page.
  const groupedReport = useQuery({
    queryKey: ["general-ledger-grouped", printParams],
    queryFn: () => getLedgerPrint(printParams),
    enabled: groupByAccount,
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });
  const printQuery = new URLSearchParams(printParams as Record<string, string>).toString();
  const printSrc = `/general-ledger/print${printQuery ? `?${printQuery}` : ""}`;

  const handleExport = async () => {
    setExportError(null);
    setExporting(true);
    try {
      await downloadGeneralLedgerReport(printParams, "general-ledger");
    } catch (error: any) {
      setExportError(error?.response?.data?.detail || "Unable to export the general ledger");
    } finally {
      setExporting(false);
    }
  };
  type AccountGroup = { id: number; code: string; name: string; rows: any[]; debit: number; credit: number; opening?: string | number; closing?: string | number };
  const pagedAccountGroups = Array.from<AccountGroup>(
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
  // The grouped report uses the print row shape; normalize it to the ledger row shape
  // so the same renderer handles both views.
  type GroupItem = { kind: "group" | "total"; group: AccountGroup; height: number } | { kind: "row"; row: any; height: number };
  const accountGroups: AccountGroup[] = groupedReport.data?.accounts?.length
    ? groupedReport.data.accounts.map((group: any) => ({
        id: Number(group.account_id),
        code: group.account_code || "—",
        name: group.account_name || "Unknown account",
        opening: group.opening_balance,
        closing: group.closing_balance,
        debit: Number(group.total_debit || 0),
        credit: Number(group.total_credit || 0),
        rows: (group.rows ?? []).map((row: any) => ({
          ...row,
          account_id: group.account_id,
          account_code: group.account_code,
          account_name: group.account_name,
          reference_number: row.document_number ?? row.reference ?? "",
          reference_type: row.document_type ?? "",
        })),
      }))
    : pagedAccountGroups;
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
    enabled: groupByAccount && !groupedReport.data?.accounts?.length && Boolean(accountGroupIds),
  });
  const accountBalanceById = new Map<number, LedgerAccountBalance>((accountBalances.data?.items ?? []).map(row => [row.account_id, row]));
  const balanceIsFiltered = Boolean(filters.search || filters.reference_type || filters.supplier_id);
  const toggleAccount = (id: number) => setCollapsedAccounts(previous => previous.includes(id) ? previous.filter(value => value !== id) : [...previous, id]);
  const groupedTotals = groupedReport.data?.control;
  const summaryAvailable = groupByAccount && groupedTotals
    ? groupedTotals.total_debit != null && groupedTotals.total_credit != null
    : ledger.data?.summary?.total_debit != null && ledger.data?.summary?.total_credit != null;
  const filteredTotals = groupByAccount && groupedTotals
    ? { debit: Number(groupedTotals.total_debit), credit: Number(groupedTotals.total_credit) }
    : summaryAvailable ? {
        debit: Number(ledger.data?.summary?.total_debit),
        credit: Number(ledger.data?.summary?.total_credit),
      } : null;
  const activeLoading = groupByAccount ? groupedReport.isLoading : ledger.isLoading;
  const activeError = groupByAccount ? groupedReport.isError : ledger.isError;
  const activeRefetch = groupByAccount ? groupedReport.refetch : ledger.refetch;
  const activeTotalItems = groupByAccount && groupedReport.data
    ? groupedReport.data.accounts.reduce((count: number, group: any) => count + (group.rows?.length ?? 0), 0)
    : (ledger.data?.total_items ?? 0);
  const groupedPending = groupByAccount && groupedReport.isLoading && !groupedReport.data;
  const balanced = filteredTotals ? Number(filteredTotals.debit) === Number(filteredTotals.credit) : null;
  const balanceStatus = balanced === null ? (activeLoading ? "Checking…" : "—") : balanced ? "Balanced" : "Out of balance";
  const summaryMetrics: SummaryMetric[] = [
    { label: "Entries", value: activeTotalItems, note: "Matching ledger entries in the selected view" },
    { label: "Accounts", value: accountGroups.length, note: "Accounts represented in the current view" },
    { label: "Debit", value: filteredTotals ? amount(filteredTotals.debit) : "—", note: "Total debit across matching entries" },
    { label: "Credit", value: filteredTotals ? amount(filteredTotals.credit) : "—", note: "Total credit across matching entries" },
    { label: "Difference", value: filteredTotals ? amount(filteredTotals.debit - filteredTotals.credit) : "—", note: "Debit minus credit across matching entries" },
  ];

  // Windowing keeps the full, correct grouped dataset in memory without mounting
  // ~19,000 table rows at once — that render cost was the main load-time spike.
  const [scrollEl, setScrollEl] = useState<HTMLElement | null>(null);
  const [scrollMargin, setScrollMargin] = useState(0);
  useEffect(() => {
    if (!groupByAccount) return;
    const el = document.querySelector<HTMLElement>(".gl-ledger-viewport");
    setScrollEl(el);
    setScrollMargin(el?.querySelector("thead")?.getBoundingClientRect().height ?? 0);
  }, [groupByAccount, denseRows]);
  const groupedItems = useMemo<GroupItem[]>(() => {
    if (!groupByAccount) return [];
    const items: GroupItem[] = [];
    for (const group of accountGroups) {
      items.push({ kind: "group", group, height: 52 });
      if (!collapsedAccounts.includes(group.id)) {
        for (const row of group.rows) items.push({ kind: "row", row, height: 32 });
        items.push({ kind: "total", group, height: 28 });
      }
    }
    return items;
  }, [groupByAccount, accountGroups, collapsedAccounts]);
  const rowVirtualizer = useVirtualizer({
    count: groupedItems.length,
    getScrollElement: () => scrollEl,
    estimateSize: (index) => groupedItems[index]?.height ?? 32,
    overscan: 8,
    scrollMargin,
  });
  const virtualRows = rowVirtualizer.getVirtualItems();

  // Cached measurements are index-based, so clear them when row sizes or item
  // positions change. Otherwise the final spacer can be wrong on density
  // changes, collapses, or a refetched report — that was the trailing blank.
  useEffect(() => {
    rowVirtualizer.measure();
  }, [denseRows, collapsedAccounts, groupedReport.data, groupByAccount, rowVirtualizer]);

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
  const renderLedgerRow = (row: any, virtualIndex?: number) => {
    const contextPrimary = row.supplier_name || row.business_unit_name;
    const contextSecondary = [row.department_name, row.location_name].filter(Boolean).join(" · ");
    return <TR key={row.id} ref={virtualIndex !== undefined ? rowVirtualizer.measureElement : undefined} data-index={virtualIndex}>
      <TD className="whitespace-nowrap">{row.posting_date}</TD>
      <TD className="whitespace-nowrap"><Link className={TABLE_UI.documentLink} to={`/journal-entries/${row.journal_id}`}>{row.journal_number}</Link></TD>
      <TD className="max-w-[200px]"><span className="inline-flex min-w-0 max-w-full items-center gap-1.5 whitespace-nowrap" title={`${row.account_code} — ${row.account_name}`}><span className="shrink-0 font-mono text-[11px] text-slate-500">{row.account_code}</span><span className="min-w-0 truncate">{row.account_name}</span></span></TD>
      <TD className="max-w-[220px]"><span className="block truncate" title={row.description || undefined}>{row.description || "—"}</span></TD>
      <TD className="max-w-[160px]">{documentLink(row) ? <Link className={TABLE_UI.documentLink} to={documentLink(row)!} title={row.reference_number || "Open source document"}>{row.reference_number || row.reference_type || "Open source"}</Link> : <span className="block truncate font-medium text-slate-700" title={row.reference_number || undefined}>{row.reference_number || "—"}</span>}</TD>
      <TD numeric className="whitespace-nowrap">{amount(row.debit)}</TD>
      <TD numeric className="whitespace-nowrap">{amount(row.credit)}</TD>
      <TD numeric className="whitespace-nowrap font-semibold">{amount(row.balance)}</TD>
      <TD className="max-w-[180px]">{contextPrimary || contextSecondary ? <TableCellStack primary={contextPrimary || contextSecondary} secondary={contextPrimary ? contextSecondary : undefined}/> : "—"}</TD>
    </TR>;
  };
  const renderGroupItem = (item: GroupItem, index: number) => {
    if (item.kind === "row") return renderLedgerRow(item.row, index);
    const group = item.group;
    const collapsed = collapsedAccounts.includes(group.id);
    const accountBalance = accountBalanceById.get(group.id);
    const opening = group.opening ?? accountBalance?.opening_balance;
    const closing = group.closing ?? accountBalance?.closing_balance;
    if (item.kind === "group") return <TR key={`group-${group.id}`} ref={rowVirtualizer.measureElement} data-index={index} className="gl-v-group bg-slate-100/80">
      <TD colSpan={9}>
        <div className="flex items-center justify-between gap-2">
          <button type="button" onClick={() => toggleAccount(group.id)} aria-expanded={!collapsed} className="gl-group-toggle flex items-center gap-2 text-left text-sm font-semibold text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A]">
            {collapsed ? <ChevronRight size={16}/> : <ChevronDown size={16}/>}<span className="font-mono text-xs text-slate-600">{group.code}</span> — {group.name}
          </button>
          <span className="text-xs font-normal text-slate-600">{group.rows.length} {group.rows.length === 1 ? "entry" : "entries"}</span>
        </div>
        <div className="mt-0.5 flex flex-wrap gap-x-5 gap-y-0 overflow-hidden text-xs text-slate-700">
          {opening != null || accountBalance ? <>
            <span>Opening: <strong>{amount(opening ?? 0)}</strong></span>
            <span>Period debit: <strong>{amount(group.debit)}</strong></span>
            <span>Period credit: <strong>{amount(group.credit)}</strong></span>
            <span>Closing: <strong>{amount(closing ?? 0)}</strong></span>
          </> : <span className="text-slate-600">{accountBalances.isLoading ? "Loading full account balances…" : "Full account balances unavailable"}</span>}
        </div>
      </TD>
    </TR>;
    return <TR key={`total-${group.id}`} ref={rowVirtualizer.measureElement} data-index={index} className="gl-v-total bg-slate-50 font-medium text-slate-700">
      <TD colSpan={5} className="text-right text-xs text-slate-600">Period total — {group.code}</TD>
      <TD numeric className="whitespace-nowrap">{amount(group.debit)}</TD>
      <TD numeric className="whitespace-nowrap">{amount(group.credit)}</TD>
      <TD colSpan={2} className="text-xs text-slate-500">Closing: {closing != null ? amount(closing) : "—"}</TD>
    </TR>;
  };
  return <DataWorkspace area="Accounting" className="print-document gl-data-first"><style>{`@page{size:landscape;margin:10mm}
    body:has(.gl-data-first) [data-workspace-content] { padding: 3px 5px !important; }
    .gl-data-first { height: calc(100dvh - 94px) !important; gap: 3px !important; }
    .gl-data-first > * { flex-shrink: 0; }
    .gl-data-first .gl-toolbar { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; flex: 0 0 auto; }
    .gl-data-first .gl-toolbar :is(input,select,button) { height: 28px !important; min-height: 28px !important; font-size: 12px !important; }
    .gl-data-first .gl-search { flex: 2 1 240px; min-width: 160px; padding: 0 8px; border: 1px solid #d5dce2; border-radius: 6px; background: white; }
    .gl-data-first .gl-date { flex: 0 1 132px; min-width: 120px; padding: 0 6px; border: 1px solid #d5dce2; border-radius: 6px; background: white; }
    .gl-data-first .gl-unit-select { flex: 0 1 140px; padding: 0 6px; border: 1px solid #d5dce2; border-radius: 6px; background: white; }
    .gl-data-first .gl-chips { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; flex: 0 0 auto; }
    .gl-data-first .gl-statusbar { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 12px; flex: 0 0 auto; padding: 4px 10px !important; border-top: 1px solid #e6ebef; background: #fafbfc; font-size: 11px; line-height: 16px; color: #52616d; }
    .gl-data-first .gl-statusbar strong { color: #1f2d38; font-variant-numeric: tabular-nums; }
    .gl-data-first .gl-statusbar select { height: 24px !important; min-height: 24px !important; }
    .gl-data-first .gl-statusbar button { height: 24px !important; min-height: 24px !important; padding: 0 8px !important; }
    .gl-data-first .workspace-data > .gl-summary { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 8px; padding: 2px 8px !important; border-top: 1px solid #e6ebef; background: #fafbfc; font-size: 11px; line-height: 16px; }
    .gl-data-first .gl-summary section { flex: 1 1 auto; min-width: 0; border: 0; background: transparent; padding: 0; }
    .gl-data-first .gl-state-alert { display: flex; flex-direction: column; align-items: flex-start; gap: 6px; padding: 8px 10px; border: 1px solid #fecaca; border-radius: 6px; background: #fef2f2; color: #b91c1c; text-align: left; }
    .gl-data-first .workspace-data { flex: 1 1 0 !important; min-height: 0 !important; }
    .gl-data-first .gl-ledger-viewport { min-height: 0 !important; max-height: none !important; }
    .gl-compact-ledger tbody tr td { padding: 3px 8px; font-size: 13px; line-height: 17px; }
    .gl-compact-ledger thead tr th { height: 26px; padding: 4px 8px; font-size: 11px; }
    .gl-compact-ledger tbody tr button { line-height: 17px; }
    .gl-compact-ledger .text-slate-400 { color: #475569 !important; }
    .gl-v-notice td { padding: 3px 10px !important; height: 24px; font-size: 11px; color: #92610a; background: #fffbeb; }
    .gl-v-group td { height: 52px; padding: 2px 10px !important; }
    .gl-v-total td { height: 28px; padding: 2px 10px !important; }
    .gl-v-spacer td { height: auto; padding: 0 !important; border: 0 !important; background: white; }
    .gl-group-toggle { min-height: 30px; }
    .gl-view-toggle button { min-height: 24px; }
    @media print { .gl-compact-ledger tbody tr td { padding: 4px 7px; font-size: 11px; } }
  `}</style>
    <PageHeader className="print:hidden" title="General Ledger" description="Posted journal activity across accounts, with grouped balances and period debit, credit, and closing totals." />
    <div className="hidden print:block"><h1 className="text-2xl font-bold">MMH-Connect</h1><h2 className="text-xl font-semibold">General Ledger</h2><p className="text-xs text-slate-600">{printHeader}</p><p className="text-xs text-slate-500">Printed {new Date().toLocaleString()}</p></div>
    <div className="gl-toolbar print:hidden">
      <input className="gl-search" aria-label="Search general ledger" placeholder="Search journal, document, description, account..." value={filters.search} onChange={event => change("search", event.target.value)}/>
      <input className="gl-date" aria-label="From date" title="From date" type="date" value={filters.date_from} onChange={event => change("date_from", event.target.value)}/>
      <input className="gl-date" aria-label="To date" title="To date" type="date" value={filters.date_to} onChange={event => change("date_to", event.target.value)}/>
      <select className="gl-unit-select" aria-label="Business unit" title="Business unit" value={filters.business_unit_id} onChange={event => { setFilters({ ...filters, business_unit_id: event.target.value, location_id: "", department_id: "" }); setPage(1); }}>
        {businessUnits.data?.map(unit => <option key={unit.id} value={unit.id}>{unit.name}</option>)}
        <option value="">Consolidated</option>
      </select>
      <Button type="button" size="md" variant="outline" title="Open transaction filters" aria-label="Open General Ledger filters" aria-expanded={showFilters} onClick={() => setShowFilters(true)}><SlidersHorizontal size={15}/><span className="sr-only">Filters</span>{activeAdvancedFilters ? <span className="text-xs">{activeAdvancedFilters}</span> : null}</Button>
      <Button type="button" size="md" variant="outline" title="Display preferences" aria-label="Ledger display preferences" onClick={() => setShowDisplayTools(true)}><Rows3 size={15}/><span className="sr-only">Display</span></Button>
      <ExportButton scope="filtered" format="excel" size="md" loading={exporting} onClick={handleExport} />
      <PrintPreviewButton src={printSrc} title="General Ledger" ariaLabel="Preview general ledger" label="Print" />
    </div>
    {activeChips.length > 0 && <div className="gl-chips print:hidden">
      {activeChips.map(chip => <button key={chip.key} type="button" onClick={() => change(chip.key, "")} title={`Remove ${chip.label} filter`} className="inline-flex min-h-6 items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-900 hover:bg-emerald-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A]">
        <span className="font-medium">{chip.label}:</span><span className="max-w-[180px] truncate">{chip.value}</span><X size={11} aria-hidden="true" />
      </button>)}
      <button type="button" onClick={clearAllChips} className="min-h-6 rounded px-1.5 text-[11px] text-slate-600 underline underline-offset-2 hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A]">Clear all</button>
    </div>}
    {exportError && <div className="rounded-md border border-red-200 bg-red-50 px-3 py-1.5 text-xs text-red-700 print:hidden">{exportError}</div>}
    <Dialog open={showFilters} onOpenChange={setShowFilters}>
      <DialogContent className="max-w-3xl">
        <DialogHeader><DialogTitle>General Ledger filters</DialogTitle></DialogHeader>
        <DialogBody>
          <p className="mb-3 text-xs text-slate-500">Filters update the report immediately. Close this panel to return to the ledger; dates and business unit remain available on the main screen.</p>
          <div className="space-y-3">

        <div className="grid gap-2 md:grid-cols-3">
          <label className="text-xs">Search Type
            <select className={`${input} mt-0.5 w-full`} value={filters.search_type} onChange={event=>change("search_type",event.target.value)}>
              <option value="ALL">All fields</option><option value="JOURNAL">Journal No.</option><option value="DOCUMENT">Document No.</option><option value="DESCRIPTION">Description</option><option value="ACCOUNT">Account</option><option value="SUPPLIER">Supplier</option>
            </select>
          </label>
          <SearchableSelect inlineDropdown maxOptions={Number.POSITIVE_INFINITY} label="Single Account" value={filters.account_id ? Number(filters.account_id) : undefined} disabled={accounts.isLoading} placeholder="Exact account..." options={(accounts.data ?? []).map((account: any) => ({ id: account.id, label: `${account.account_code} — ${account.account_name}${account.is_active ? "" : " (Inactive)"}`, keywords: [account.account_code ?? "", account.account_name ?? ""] }))} onChange={(id) => change("account_id", id ? String(id) : "")} />
          <select className={input} aria-label="Document type" value={filters.reference_type} onChange={event => change("reference_type", event.target.value)}><option value="">All document types</option><option>SUPPLIER_INVOICE</option><option>SUPPLIER_PAYMENT</option><option>MANUAL</option></select>
        </div>
        <div className="grid gap-2 md:grid-cols-2">
          <SearchableSelect inlineDropdown dropdownPlacement="top" maxOptions={Number.POSITIVE_INFINITY} label="From Account" value={filters.account_from_id ? Number(filters.account_from_id) : undefined} disabled={accounts.isLoading || Boolean(filters.account_id)} placeholder="Start account..." options={(accounts.data ?? []).map((account: any) => ({ id: account.id, label: `${account.account_code} — ${account.account_name}${account.is_active ? "" : " (Inactive)"}`, keywords: [account.account_code ?? "", account.account_name ?? ""] }))} onChange={(id) => change("account_from_id", id ? String(id) : "")} />
          <SearchableSelect inlineDropdown dropdownPlacement="top" maxOptions={Number.POSITIVE_INFINITY} label="To Account" value={filters.account_to_id ? Number(filters.account_to_id) : undefined} disabled={accounts.isLoading || Boolean(filters.account_id)} placeholder="End account..." options={(accounts.data ?? []).map((account: any) => ({ id: account.id, label: `${account.account_code} — ${account.account_name}${account.is_active ? "" : " (Inactive)"}`, keywords: [account.account_code ?? "", account.account_name ?? ""] }))} onChange={(id) => change("account_to_id", id ? String(id) : "")} />
        </div>
        <div className="grid gap-2 md:grid-cols-3">
          <SearchableSelect inlineDropdown dropdownPlacement="top" label="Supplier" value={filters.supplier_id ? Number(filters.supplier_id) : undefined} disabled={suppliers.isLoading} placeholder="Select supplier..." options={(suppliers.data ?? []).map(item => ({ id: item.id, label: `${item.code} — ${item.name}`, keywords: [item.code, item.name] }))} onChange={id => change("supplier_id", id ? String(id) : "")}/>
          <SearchableSelect inlineDropdown dropdownPlacement="top" label="Department" value={filters.department_id ? Number(filters.department_id) : undefined} disabled={departments.isLoading} placeholder="Select department..." options={(departments.data ?? []).map(item => ({ id: item.id, label: `${item.code} — ${item.name}`, keywords: [item.code, item.name] }))} onChange={id => change("department_id", id ? String(id) : "")}/>
          <SearchableSelect inlineDropdown dropdownPlacement="top" label="Location" value={filters.location_id ? Number(filters.location_id) : undefined} disabled={locations.isLoading} placeholder={locations.isLoading ? "Loading locations..." : "Type location code or name..."} options={(locations.data ?? []).map((item: any) => ({ id: item.id, label: `${item.code} — ${item.name}`, keywords: [item.code ?? "", item.name ?? ""] }))} onChange={(id) => change("location_id", id ? String(id) : "")} />
        </div>

          </div>
        </DialogBody>
        <DialogFooter><div className="flex w-full items-center justify-between gap-2">
          <button type="button" className="rounded border border-slate-200 px-3 py-1.5 text-xs text-slate-700 hover:bg-slate-50" onClick={() => {
            setFilters((current: any) => ({...current, search_type: "ALL", account_id: "", account_ids: "", account_from_id: "", account_to_id: "", reference_type: "", supplier_id: "", department_id: "", location_id: ""}));
            setPage(1);
          }}>Clear advanced filters</button>
          <Button type="button" size="sm" onClick={() => setShowFilters(false)}>Close</Button>
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
    <Card className="workspace-data">
      <Table variant="grid" stickyHeader className={`workspace-ledger-table min-w-[980px] ${denseRows ? "gl-compact-ledger" : ""}`} containerClassName="gl-ledger-viewport overflow-auto border-0 shadow-none print:max-h-none print:min-h-0 print:overflow-visible">
        <THead><TR className="whitespace-nowrap"><TH>Date</TH><TH>Journal</TH><TH>Account</TH><TH>Description</TH><TH>Document</TH><TH numeric>Debit</TH><TH numeric>Credit</TH><TH numeric>Balance</TH><TH>Context</TH></TR></THead>
        <TBody>
          {activeLoading && !accountGroups.length && <GlTableSkeleton />}
          {groupedPending && accountGroups.length > 0 && <TR className="gl-v-notice"><TD colSpan={9}><Loading size="sm" className="py-0" message="Loading complete account data… showing this page until all entries are ready." /></TD></TR>}
          {activeError && !accountGroups.length && <TR><TD colSpan={9}><div role="alert" className="gl-state-alert">
            <div className="font-semibold">Ledger could not be loaded.</div>
            <p className="text-xs">{apiErrorMessage(groupByAccount ? groupedReport.error : ledger.error, "Unable to load the general ledger.")}</p>
            <Button size="sm" variant="outline" onClick={() => activeRefetch()}><RotateCw size={14}/> Retry</Button>
          </div></TD></TR>}
          {!activeLoading && !activeError && !accountGroups.length && <TR><TD colSpan={9}><Empty className="border-0 bg-transparent py-8" title="No entries match these filters." description="Adjust the date range, accounts, or document filters to see ledger activity." action={<Button size="sm" variant="outline" onClick={() => setShowFilters(true)}>Adjust filters</Button>} /></TD></TR>}
          {!activeLoading && !activeError && !groupByAccount && (ledger.data?.items ?? []).map(renderLedgerRow)}
          {!activeError && groupByAccount && scrollEl && groupedItems.length > 0 && (() => {
            const paddingTop = Math.max(0, (virtualRows[0]?.start ?? 0) - scrollMargin);
            const paddingBottom = Math.max(0, rowVirtualizer.getTotalSize() - scrollMargin - (virtualRows[virtualRows.length - 1]?.end ?? 0));
            return <>
              {paddingTop > 0 && <TR className="gl-v-spacer"><TD colSpan={9} style={{ height: paddingTop }} /></TR>}
              {virtualRows.map(virtualRow => renderGroupItem(groupedItems[virtualRow.index], virtualRow.index))}
              {paddingBottom > 0 && <TR className="gl-v-spacer"><TD colSpan={9} style={{ height: paddingBottom }} /></TR>}
            </>;
          })()}
        </TBody>
      </Table>
      <div className="gl-summary print:hidden" aria-label="Ledger summary">
        <ModuleSummary metrics={summaryMetrics} />
        <Badge variant={balanced === null ? "secondary" : balanced ? "success" : "danger"}>{balanceStatus}</Badge>
      </div>
      <div className="gl-statusbar print:hidden">
        <span><strong>{activeTotalItems}</strong> entries{groupByAccount ? groupedPending ? " · reconciling…" : " · all shown" : ""}</span>
        <span>Debit <strong>{filteredTotals ? amount(filteredTotals.debit) : activeLoading ? "…" : "—"}</strong></span>
        <span>Credit <strong>{filteredTotals ? amount(filteredTotals.credit) : activeLoading ? "…" : "—"}</strong></span>
        <span className="inline-flex items-center gap-1">Diff <strong>{filteredTotals ? <Link to={unbalancedJournalPath(filters)} title="Difference across all matching entries — review unbalanced journals in this period and scope." className="text-emerald-700 hover:underline">{amount(filteredTotals.debit - filteredTotals.credit)}</Link> : "…"}</strong><Info size={11} aria-hidden="true" /></span>
        {summary.data && <span title="Account activity for the selected account and period">Account closing <strong>{amount(summary.data.closing_balance)}</strong></span>}
        {balanceIsFiltered && <span title="Running balances include complete account movements; debit/credit totals cover matching entries only." className="cursor-help text-amber-800">⚠ filtered balance</span>}
        <div className="gl-view-toggle inline-flex items-center gap-1 rounded-md border border-slate-200 p-0.5 ml-auto" role="group" aria-label="Ledger display mode">
          <button type="button" onClick={() => setGroupByAccount(true)} aria-pressed={groupByAccount} title="Group by account" className={`flex items-center gap-1 rounded px-2 py-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A] ${groupByAccount ? "bg-slate-800 text-white" : "text-slate-600 hover:bg-slate-100"}`}><Layers3 size={13}/> By account</button>
          <button type="button" onClick={() => setGroupByAccount(false)} aria-pressed={!groupByAccount} title="Show transactions" className={`flex items-center gap-1 rounded px-2 py-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A] ${!groupByAccount ? "bg-slate-800 text-white" : "text-slate-600 hover:bg-slate-100"}`}><List size={13}/> Transactions</button>
        </div>
        <span>Page {page}/{Math.max(ledger.data?.total_pages ?? 0, 1)}</span>
        <label className="inline-flex items-center gap-1">Rows <select className="rounded border border-slate-300 bg-white px-1" value={pageSize} onChange={e => { setPageSize(Number(e.target.value)); setPage(1); }}><option value={50}>50</option><option value={100}>100</option></select></label>
        <Button size="md" variant="outline" title="Previous page" aria-label="Previous page" disabled={!ledger.data?.has_previous} onClick={() => setPage(page - 1)}>‹</Button>
        <Button size="md" variant="outline" title="Next page" aria-label="Next page" disabled={!ledger.data?.has_next} onClick={() => setPage(page + 1)}>›</Button>
      </div>
      <p className="px-2 pb-1 text-[10px] text-slate-600 sm:hidden print:hidden">Scroll sideways to see all columns →</p>
    </Card>
  </DataWorkspace>;
}

