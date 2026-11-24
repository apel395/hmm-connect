import { useEffect, useMemo, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import useAuthStore from "@/store/auth";
import { exportCsv } from "@/utils/exportCsv";
import ListToolbar from "@/components/common/ListToolbar";
import ModuleSummary, { type SummaryMetric } from "@/components/common/ModuleSummary";
import PageHeader from "@/components/common/PageHeader";
import Pagination from "@/components/datatable/Pagination";
import Badge, { type BadgeVariant } from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card, { CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { useFinanceList } from "@/modules/finance/hooks/useFinanceList";
import ARImportStagingDialog from "./ARImportStagingDialog";
import ARWorkspaceHeader from "./ARWorkspaceHeader";
import { arReportingApi, type ARDetail, type ARStatus, type AgingBucket } from "./reportingApi";

const money = (value: unknown) =>
  `Rp ${Number(value || 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const statusVariant = (status: ARStatus): BadgeVariant =>
  status === "PAID" ? "success" : status === "PARTIALLY_PAID" ? "warning" : "danger";

const statusLabel: Record<ARStatus, string> = {
  PAID: "Paid",
  PARTIALLY_PAID: "Partially Paid",
  UNPAID: "Unpaid",
};

const bucketLabels: Record<AgingBucket, string> = {
  current: "Current",
  "1_30": "1–30 Days",
  "31_60": "31–60 Days",
  "61_90": "61–90 Days",
  over_90: "Over 90 Days",
};

const bucketKeys = Object.keys(bucketLabels) as AgingBucket[];

export default function ARReportingPage() {
  const location = useLocation();
  const canManage = useAuthStore((store) => store.hasPermission("finance.manage"));
  const [importOpen, setImportOpen] = useState(false);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<ARStatus | "ALL">("ALL");

  const section = location.pathname.endsWith("/detail")
    ? "detail"
    : location.pathname.endsWith("/aging")
      ? "aging"
      : "summary";

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  const filters = useMemo(
    () => ({
      section,
      search,
      status: status === "ALL" ? undefined : status,
    }),
    [section, search, status],
  );

  const detail = useFinanceList<ARDetail>({
    queryKey: ["ar-reporting", "detail"],
    filters,
    enabled: section === "detail",
    queryFn: ({ page, page_size, search: activeSearch, status: activeStatus }) =>
      arReportingApi.detail(
        page,
        page_size,
        String(activeSearch ?? ""),
        activeStatus as ARStatus | undefined,
      ),
  });
  const { page, pageSize, setPage, setPageSize } = detail;

  const summary = useQuery({
    queryKey: ["ar-reporting", "summary", page, pageSize, search],
    queryFn: () => arReportingApi.summary(page, pageSize, search),
    enabled: section === "summary",
  });
  const aging = useQuery({
    queryKey: ["ar-reporting", "aging", page, pageSize, search],
    queryFn: () => arReportingApi.aging(page, pageSize, search),
    enabled: section === "aging",
  });

  const activeQuery = section === "detail" ? detail : section === "aging" ? aging : summary;
  const activeData = activeQuery.data;
  const total = activeData?.total_items ?? 0;

  const metrics = useMemo<SummaryMetric[]>(() => {
    if (section === "summary" && summary.data) {
      const { metrics: values } = summary.data;
      return [
        { label: "Gross", value: money(values.gross_receivables) },
        { label: "Receipts", value: money(values.total_receipts) },
        { label: "Outstanding", value: money(values.outstanding_receivables) },
        { label: "Overdue", value: money(values.overdue_receivables) },
        { label: "Customers", value: values.customer_count },
        { label: "Invoices", value: values.invoice_count },
      ];
    }
    if (section === "detail" && detail.data) {
      const rows = detail.data.items;
      return [
        { label: "Invoices on page", value: rows.length },
        {
          label: "Outstanding on page",
          value: money(rows.reduce((sum, row) => sum + Number(row.outstanding_amount || 0), 0)),
        },
        { label: "Paid", value: rows.filter((row) => row.status === "PAID").length },
        { label: "Partially paid", value: rows.filter((row) => row.status === "PARTIALLY_PAID").length },
        { label: "Unpaid", value: rows.filter((row) => row.status === "UNPAID").length },
      ];
    }
    if (section === "aging" && aging.data) {
      return [
        { label: "Total outstanding", value: money(aging.data.total_outstanding) },
        { label: "As of", value: aging.data.as_of_date },
        { label: "Customers", value: aging.data.items.length },
        { label: "Over 90 days", value: money(aging.data.buckets.over_90.amount) },
      ];
    }
    return [];
  }, [section, summary.data, detail.data, aging.data]);

  const exportPage = () => {
    if (section === "summary" && summary.data) {
      exportCsv(
        "ar-summary.csv",
        ["Customer", "Code", "Gross", "Receipts", "Outstanding", "Invoices", "Overdue Invoices", "Status"],
        summary.data.items.map((row) => [
          row.customer_name ?? `Customer #${row.customer_id}`,
          row.customer_code,
          row.gross_amount,
          row.received_amount,
          row.outstanding_amount,
          row.invoice_count,
          row.overdue_invoice_count,
          statusLabel[row.status],
        ]),
      );
      return;
    }
    if (section === "detail" && detail.data) {
      exportCsv(
        "ar-detail.csv",
        ["Invoice", "Date", "Customer", "Due Date", "Gross", "Receipts", "Outstanding", "Status"],
        detail.data.items.map((row) => [
          row.invoice_number,
          row.invoice_date,
          row.customer_name ?? `Customer #${row.customer_id}`,
          row.due_date,
          row.gross_amount,
          row.received_amount,
          row.outstanding_amount,
          statusLabel[row.status],
        ]),
      );
      return;
    }
    if (section === "aging" && aging.data) {
      exportCsv(
        "ar-aging.csv",
        ["Customer", "Code", ...bucketKeys.map((bucket) => bucketLabels[bucket]), "Outstanding"],
        aging.data.items.map((row) => [
          row.customer_name ?? `Customer #${row.customer_id}`,
          row.customer_code,
          ...bucketKeys.map((bucket) => row[bucket]),
          row.outstanding_amount,
        ]),
      );
    }
  };

  const statusSelect = (
    <select
      aria-label="Collection status"
      className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm"
      value={status}
      onChange={(event) => setStatus(event.target.value as ARStatus | "ALL")}
    >
      <option value="ALL">All statuses</option>
      {(Object.keys(statusLabel) as ARStatus[]).map((value) => (
        <option key={value} value={value}>
          {statusLabel[value]}
        </option>
      ))}
    </select>
  );

  const sectionTitle =
    section === "detail" ? "Receivables Detail" : section === "aging" ? "AR Aging" : "Receivables Summary";
  const sectionDescription =
    section === "detail"
      ? "Invoice-level balances and collection status."
      : section === "aging"
        ? `Outstanding customer balances as of ${aging.data?.as_of_date ?? "today"}.`
        : "Customer balances from the Accounts Receivable subledger.";

  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="space-y-2">
        <PageHeader
          title={sectionTitle}
          description={sectionDescription}
          actions={
            canManage ? (
              <Button size="sm" variant="outline" onClick={() => setImportOpen(true)}>
                Stage AR Excel
              </Button>
            ) : undefined
          }
        >
          <div className="mt-0.5 text-[11px] text-slate-500">
            Read-only AR reporting · current-page export available
          </div>
        </PageHeader>
        <ARWorkspaceHeader />
        {canManage && <ARImportStagingDialog open={importOpen} onOpenChange={setImportOpen} />}
        {!!metrics.length && <ModuleSummary metrics={metrics} />}

        <Card className="overflow-hidden p-0">
          <div className="p-3 print:hidden">
            <ListToolbar
              search={searchInput}
              searchPlaceholder={section === "detail" ? "Search invoice or customer..." : "Search customer..."}
              onSearch={setSearchInput}
              filters={section === "detail" ? statusSelect : undefined}
              onExport={exportPage}
              onRefresh={() => activeQuery.refetch()}
              footer={
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span>{total} {section === "detail" ? "invoices" : "customers"} match current filters</span>
                  <label className="inline-flex items-center gap-1">
                    Rows per page
                    <select
                      aria-label="Rows per page"
                      className="ml-1 rounded border border-slate-300 bg-white px-2 py-1"
                      value={pageSize}
                      onChange={(event) => setPageSize(Number(event.target.value))}
                    >
                      <option value={50}>50</option>
                      <option value={100}>100</option>
                    </select>
                  </label>
                </div>
              }
            />
          </div>

          {activeQuery.isPending ? (
            <Loading message="Loading Accounts Receivable report..." />
          ) : activeQuery.isError ? (
            <div role="alert" className="m-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <div className="font-semibold">Accounts Receivable reporting could not be loaded.</div>
              <Button className="mt-3" size="sm" variant="outline" onClick={() => activeQuery.refetch()}>
                Try again
              </Button>
            </div>
          ) : (
            <>
              {section === "summary" && summary.data && (
                <>
                  <CardHeader>
                    <div>
                      <CardTitle className="text-sm">Receivables by Customer</CardTitle>
                      <CardDescription>Customer balances from the AR subledger.</CardDescription>
                    </div>
                  </CardHeader>
                  <Table className="min-w-[900px]" containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
                    <THead>
                      <TR>
                        <TH>Customer</TH>
                        <TH numeric>Gross</TH>
                        <TH numeric>Receipts</TH>
                        <TH numeric>Outstanding</TH>
                        <TH numeric>Overdue Invoices</TH>
                        <TH>Status</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {summary.data.items.map((row) => (
                        <TR key={row.customer_id}>
                          <TD>
                            <TableCellStack
                              primary={row.customer_name || `Customer #${row.customer_id}`}
                              secondary={`${row.customer_code || "—"} · ${row.invoice_count} invoices`}
                            />
                          </TD>
                          <TD numeric>{money(row.gross_amount)}</TD>
                          <TD numeric>{money(row.received_amount)}</TD>
                          <TD numeric className="font-semibold tabular-nums">{money(row.outstanding_amount)}</TD>
                          <TD numeric>{row.overdue_invoice_count}</TD>
                          <TD><Badge variant={statusVariant(row.status)}>{statusLabel[row.status]}</Badge></TD>
                        </TR>
                      ))}
                      {!summary.data.items.length && (
                        <TR><TD colSpan={6} className="p-10 text-center text-slate-500">No receivables found.</TD></TR>
                      )}
                    </TBody>
                  </Table>
                </>
              )}

              {section === "detail" && detail.data && (
                <>
                  <CardHeader>
                    <div>
                      <CardTitle className="text-sm">Receivables Detail</CardTitle>
                      <CardDescription>Invoice-level customer balances and collection status.</CardDescription>
                    </div>
                  </CardHeader>
                  <Table className="min-w-[1000px]" containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
                    <THead>
                      <TR>
                        <TH>Date</TH>
                        <TH>Invoice</TH>
                        <TH>Customer</TH>
                        <TH>Due Date</TH>
                        <TH numeric>Gross</TH>
                        <TH numeric>Receipts</TH>
                        <TH numeric>Outstanding</TH>
                        <TH>Status</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {detail.data.items.map((row) => (
                        <TR key={row.invoice_id}>
                          <TD>{row.invoice_date}</TD>
                          <TD>
                            <Link className="font-medium text-emerald-700 hover:underline" to={`/accounts-receivable/invoices/${row.invoice_id}`}>
                              {row.invoice_number}
                            </Link>
                          </TD>
                          <TD>
                            <TableCellStack
                              primary={row.customer_name || `Customer #${row.customer_id}`}
                              secondary={row.customer_code || undefined}
                            />
                          </TD>
                          <TD>{row.due_date || "—"}</TD>
                          <TD numeric>{money(row.gross_amount)}</TD>
                          <TD numeric>{money(row.received_amount)}</TD>
                          <TD numeric className="font-semibold tabular-nums">{money(row.outstanding_amount)}</TD>
                          <TD><Badge variant={statusVariant(row.status)}>{statusLabel[row.status]}</Badge></TD>
                        </TR>
                      ))}
                      {!detail.data.items.length && (
                        <TR><TD colSpan={8} className="p-10 text-center text-slate-500">No receivable invoices found.</TD></TR>
                      )}
                    </TBody>
                  </Table>
                </>
              )}

              {section === "aging" && aging.data && (
                <>
                  <CardHeader>
                    <div>
                      <CardTitle className="text-sm">AR Aging</CardTitle>
                      <CardDescription>Outstanding customer balances as of {aging.data.as_of_date}.</CardDescription>
                    </div>
                  </CardHeader>
                  <Table className="min-w-[1000px]" containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
                    <THead>
                      <TR>
                        <TH>Customer</TH>
                        {bucketKeys.map((bucket) => <TH key={bucket} numeric>{bucketLabels[bucket]}</TH>)}
                        <TH numeric>Outstanding</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {aging.data.items.map((row) => (
                        <TR key={row.customer_id}>
                          <TD>
                            <TableCellStack
                              primary={row.customer_name || `Customer #${row.customer_id}`}
                              secondary={row.customer_code || undefined}
                            />
                          </TD>
                          {bucketKeys.map((bucket) => <TD key={bucket} numeric>{money(row[bucket])}</TD>)}
                          <TD numeric className="font-semibold tabular-nums">{money(row.outstanding_amount)}</TD>
                        </TR>
                      ))}
                      {!aging.data.items.length && (
                        <TR><TD colSpan={bucketKeys.length + 2} className="p-10 text-center text-slate-500">No outstanding receivables.</TD></TR>
                      )}
                    </TBody>
                  </Table>
                </>
              )}

              <div className="px-3 pb-2">
                <Pagination
                  page={page}
                  pages={activeData?.total_pages ?? 1}
                  total={total}
                  pageSize={pageSize}
                  noun={section === "detail" ? "invoices" : "customers"}
                  onChange={setPage}
                />
              </div>
            </>
          )}
        </Card>
      </div>
    </DataWorkspace>
  );
}
