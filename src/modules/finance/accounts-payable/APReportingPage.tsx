import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import ReportUnitButtons from "@/components/reports/ReportUnitButtons";
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
import { exportCsv } from "@/utils/exportCsv";
import APWorkspaceHeader from "./APWorkspaceHeader";
import { apReportingApi, type APStatus } from "./reportingApi";

const money = (value: unknown) =>
  `Rp ${Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const statusVariant = (status: APStatus): BadgeVariant =>
  status === "PAID" ? "success" : status === "PARTIALLY_PAID" ? "warning" : "danger";

const statusLabel: Record<APStatus, string> = {
  PAID: "Paid",
  PARTIALLY_PAID: "Partially Paid",
  UNPAID: "Unpaid",
};

export default function APReportingPage() {
  const location = useLocation();
  const isDetail = location.pathname.endsWith("/detail");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [unit, setUnit] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<APStatus | "ALL">("ALL");

  useEffect(() => {
    const timer = window.setTimeout(() => setSearch(searchInput.trim()), 300);
    return () => window.clearTimeout(timer);
  }, [searchInput]);

  useEffect(() => setPage(1), [isDetail, unit, search, status, pageSize]);

  const businessUnitId = Number(unit) || undefined;
  const summary = useQuery({
    queryKey: ["ap-reporting", "summary", page, pageSize, unit, search],
    queryFn: () => apReportingApi.summary({ page, pageSize, businessUnitId, search }),
    enabled: !isDetail,
  });
  const detail = useQuery({
    queryKey: ["ap-reporting", "detail", page, pageSize, unit, search, status],
    queryFn: () =>
      apReportingApi.detail({
        page,
        pageSize,
        businessUnitId,
        search,
        status: status === "ALL" ? undefined : status,
      }),
    enabled: isDetail,
  });

  const activeQuery = isDetail ? detail : summary;
  const data = activeQuery.data;

  const metrics: SummaryMetric[] = [];
  if (!isDetail && summary.data) {
    const values = summary.data.metrics;
    metrics.push(
      { label: "Gross", value: money(values.gross_payables) },
      { label: "Payments", value: money(values.total_payments) },
      { label: "Adjustments", value: money(values.total_adjustments) },
      { label: "Outstanding", value: money(values.outstanding_payables) },
      { label: "Suppliers", value: values.supplier_count },
      { label: "Invoices", value: values.invoice_count },
    );
  } else if (isDetail && detail.data) {
    const rows = detail.data.items;
    metrics.push(
      { label: "Invoices on page", value: rows.length },
      {
        label: "Outstanding on page",
        value: money(rows.reduce((total, row) => total + Number(row.outstanding_amount || 0), 0)),
      },
      { label: "Paid", value: rows.filter((row) => row.status === "PAID").length },
      { label: "Partially paid", value: rows.filter((row) => row.status === "PARTIALLY_PAID").length },
      { label: "Unpaid", value: rows.filter((row) => row.status === "UNPAID").length },
    );
  }

  const exportPage = () => {
    if (!isDetail && summary.data) {
      exportCsv(
        "ap-summary.csv",
        ["Supplier", "Code", "Gross", "Payments", "Adjustments", "Outstanding", "Invoices", "Status"],
        summary.data.items.map((row) => [
          row.supplier_name ?? `Supplier #${row.supplier_id}`,
          row.supplier_code,
          row.gross_amount,
          row.paid_amount,
          row.adjustment_amount,
          row.outstanding_amount,
          row.invoice_count,
          statusLabel[row.status],
        ]),
      );
      return;
    }
    if (isDetail && detail.data) {
      exportCsv(
        "ap-detail.csv",
        ["Invoice", "Date", "Supplier", "Supplier Ref", "Due Date", "Gross", "Payments", "Adjustments", "Outstanding", "Status"],
        detail.data.items.map((row) => [
          row.invoice_number,
          row.invoice_date,
          row.supplier_name ?? `Supplier #${row.supplier_id}`,
          row.supplier_invoice_number,
          row.due_date,
          row.gross_amount,
          row.paid_amount,
          row.adjustment_amount,
          row.outstanding_amount,
          statusLabel[row.status],
        ]),
      );
    }
  };

  const statusSelect = (
    <select
      aria-label="Settlement status"
      className="h-9 rounded-md border border-slate-300 bg-white px-3 text-sm"
      value={status}
      onChange={(event) => setStatus(event.target.value as APStatus | "ALL")}
    >
      <option value="ALL">All statuses</option>
      {(Object.keys(statusLabel) as APStatus[]).map((value) => (
        <option key={value} value={value}>
          {statusLabel[value]}
        </option>
      ))}
    </select>
  );

  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="space-y-2">
        <PageHeader
          title={isDetail ? "Payables Detail" : "Payables Summary"}
          description={
            isDetail
              ? "Invoice-level supplier liability and settlement history."
              : "Posted supplier invoices summarized by supplier."
          }
          actions={
            <Link
              className="inline-flex h-8 items-center rounded border border-slate-200 px-3 text-xs text-slate-700 hover:bg-slate-50"
              to="/accounts-payable/aging"
            >
              View Aging
            </Link>
          }
        >
          <div className="mt-0.5 text-[11px] text-slate-500">Read-only AP reporting · current-page export available</div>
        </PageHeader>
        <APWorkspaceHeader />
        {!!metrics.length && <ModuleSummary metrics={metrics} />}

        <Card className="overflow-hidden p-0">
          <div className="space-y-2 p-3 print:hidden">
            <ReportUnitButtons value={unit} onChange={setUnit} />
            <ListToolbar
              search={searchInput}
              searchPlaceholder={isDetail ? "Search invoice or supplier..." : "Search supplier..."}
              onSearch={setSearchInput}
              filters={isDetail ? statusSelect : undefined}
              onExport={exportPage}
              onRefresh={() => activeQuery.refetch()}
              footer={
                <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span>
                    {data?.total_items ?? 0} {isDetail ? "invoices" : "suppliers"} match current filters
                  </span>
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
            <Loading message="Loading Accounts Payable report..." />
          ) : activeQuery.isError ? (
            <div role="alert" className="m-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <div className="font-semibold">Accounts Payable reporting could not be loaded.</div>
              <Button className="mt-3" size="sm" variant="outline" onClick={() => activeQuery.refetch()}>
                Try again
              </Button>
            </div>
          ) : (
            <>
              {!isDetail && summary.data && (
                <>
                  <CardHeader>
                    <div>
                      <CardTitle className="text-sm">Payables by Supplier</CardTitle>
                      <CardDescription>Posted supplier invoices summarized by supplier.</CardDescription>
                    </div>
                  </CardHeader>
                  <Table className="min-w-[950px]" containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
                    <THead>
                      <TR>
                        <TH>Supplier</TH>
                        <TH numeric>Gross</TH>
                        <TH numeric>Payments</TH>
                        <TH numeric>Adjustments</TH>
                        <TH numeric>Outstanding</TH>
                        <TH>Status</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {summary.data.items.map((row) => (
                        <TR key={row.supplier_id}>
                          <TD>
                            <TableCellStack
                              primary={row.supplier_name || `Supplier #${row.supplier_id}`}
                              secondary={`${row.supplier_code || "—"} · ${row.invoice_count} invoices`}
                            />
                          </TD>
                          <TD numeric>{money(row.gross_amount)}</TD>
                          <TD numeric>{money(row.paid_amount)}</TD>
                          <TD numeric>{money(row.adjustment_amount)}</TD>
                          <TD numeric className="font-semibold tabular-nums">{money(row.outstanding_amount)}</TD>
                          <TD><Badge variant={statusVariant(row.status)}>{statusLabel[row.status]}</Badge></TD>
                        </TR>
                      ))}
                      {!summary.data.items.length && (
                        <TR><TD colSpan={6} className="p-10 text-center text-slate-500">No posted supplier invoices.</TD></TR>
                      )}
                    </TBody>
                  </Table>
                </>
              )}

              {isDetail && detail.data && (
                <>
                  <CardHeader>
                    <div>
                      <CardTitle className="text-sm">Payables Detail</CardTitle>
                      <CardDescription>Invoice-level supplier liability and payment history.</CardDescription>
                    </div>
                  </CardHeader>
                  <Table className="min-w-[1100px]" containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
                    <THead>
                      <TR>
                        <TH>Date</TH>
                        <TH>Invoice</TH>
                        <TH>Supplier</TH>
                        <TH>Due Date</TH>
                        <TH numeric>Gross</TH>
                        <TH numeric>Payments</TH>
                        <TH numeric>Adjustments</TH>
                        <TH numeric>Outstanding</TH>
                        <TH>Status</TH>
                      </TR>
                    </THead>
                    <TBody>
                      {detail.data.items.map((row) => (
                        <TR key={row.invoice_id}>
                          <TD>{row.invoice_date}</TD>
                          <TD>
                            <TableCellStack
                              primary={
                                <Link className="font-medium text-emerald-700 hover:underline" to={`/supplier-invoices/${row.invoice_id}`}>
                                  {row.invoice_number}
                                </Link>
                              }
                              secondary={`Supplier ref: ${row.supplier_invoice_number}`}
                            />
                          </TD>
                          <TD>
                            <TableCellStack
                              primary={row.supplier_name || `Supplier #${row.supplier_id}`}
                              secondary={row.supplier_code || undefined}
                            />
                          </TD>
                          <TD>{row.due_date || "—"}</TD>
                          <TD numeric>{money(row.gross_amount)}</TD>
                          <TD numeric>{money(row.paid_amount)}</TD>
                          <TD numeric>{money(row.adjustment_amount)}</TD>
                          <TD numeric className="font-semibold tabular-nums">{money(row.outstanding_amount)}</TD>
                          <TD><Badge variant={statusVariant(row.status)}>{statusLabel[row.status]}</Badge></TD>
                        </TR>
                      ))}
                      {!detail.data.items.length && (
                        <TR><TD colSpan={9} className="p-10 text-center text-slate-500">No posted supplier invoices.</TD></TR>
                      )}
                    </TBody>
                  </Table>
                </>
              )}

              <div className="px-3 pb-2">
                <Pagination
                  page={page}
                  pages={data?.total_pages ?? 1}
                  total={data?.total_items ?? 0}
                  pageSize={pageSize}
                  noun={isDetail ? "invoices" : "suppliers"}
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
