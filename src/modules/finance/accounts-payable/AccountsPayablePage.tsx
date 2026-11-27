import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";
import { AlertCircle } from "lucide-react";
import api from "@/api/interceptor";
import ModuleSummary, { type SummaryMetric } from "@/components/common/ModuleSummary";
import PageHeader from "@/components/common/PageHeader";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import Badge, { type BadgeVariant } from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card, { CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import { Table, TBody, TD, TH, THead, TR, TableCellStack } from "@/components/ui/Table";
import DataWorkspace from "@/components/workspace/DataWorkspace";
import { apiErrorMessage } from "@/utils/apiError";
import APWorkspaceHeader from "./APWorkspaceHeader";
import { agingDateRangeParams, inAgingDateRange, type AgingDateRange } from "./agingFilters";

type PayableRow = {
  id: number;
  supplier_invoice_id?: number;
  invoice_number: string | null;
  supplier_invoice_number?: string | null;
  supplier_id: number;
  supplier_name?: string | null;
  invoice_date?: string | null;
  due_date: string | null;
  amount: number | string;
  paid_amount: number | string;
  outstanding: number | string;
  payment_status?: string;
  last_payment_date?: string | null;
  days_overdue?: number;
  aging_bucket?: string;
  current?: number | string;
  "1_30"?: number | string;
  "31_60"?: number | string;
  "61_90"?: number | string;
  over_90?: number | string;
};
type BucketSummary = { amount: number | string; invoice_count: number; supplier_count: number; percentage: number };
type AgingResponse = {
  summary: Record<"current" | "1_30" | "31_60" | "61_90" | "over_90", number | string>;
  metrics: {
    total_outstanding: number | string;
    due_today: number | string;
    overdue_total: number | string;
    overdue_invoice_count: number;
    open_invoice_count: number;
    supplier_count: number;
    average_overdue_days: number;
  };
  buckets: Record<string, BucketSummary>;
  top_suppliers: Array<{
    supplier_id: number;
    supplier_name?: string | null;
    outstanding: number | string;
    invoice_count: number;
    overdue: number | string;
  }>;
  details: PayableRow[];
  paid: PayableRow[];
  opening_unassigned?: boolean;
};

const money = (value: unknown) =>
  `Rp ${Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const bucketLabel: Record<string, string> = {
  current: "Current",
  "1_30": "1–30 Days",
  "31_60": "31–60 Days",
  "61_90": "61–90 Days",
  over_90: "Over 90 Days",
};
const bucketKeys = Object.keys(bucketLabel);

const bucketVariant = (bucket: string): BadgeVariant =>
  bucket === "current" ? "success" : bucket === "over_90" ? "danger" : "warning";

const InvoiceLink = ({ row }: { row: PayableRow }) => {
  const id = row.supplier_invoice_id ?? row.id;
  return (
    <Link className="font-medium text-emerald-700 hover:underline" to={`/supplier-invoices/${id}`}>
      {row.invoice_number || "—"}
    </Link>
  );
};

export default function AccountsPayablePage() {
  const location = useLocation();
  const isAging = location.pathname.endsWith("/aging");
  const [agingTab, setAgingTab] = useState<"OPEN" | "PAID">("OPEN");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const aging = useQuery({ queryKey: ["accounts-payable-aging"], queryFn: async () => (await api.get<AgingResponse>("/ap-aging")).data });

  const invalidRange = Boolean(dateFrom && dateTo && dateFrom > dateTo);
  const range = useMemo<AgingDateRange>(
    () => (invalidRange ? {} : { date_from: dateFrom, date_to: dateTo }),
    [invalidRange, dateFrom, dateTo],
  );
  const dateFilterActive = Boolean(range.date_from || range.date_to);
  const printSrc = useMemo(() => {
    const search = agingDateRangeParams(range).toString();
    return `/accounts-payable/aging/print${search ? `?${search}` : ""}`;
  }, [range]);

  const agingData = useMemo(() => {
    const source = aging.data;
    if (!source || !dateFilterActive) return source;
    const details = (source.details ?? []).filter((row) => inAgingDateRange(row.invoice_date, range));
    const paid = (source.paid ?? []).filter((row) => inAgingDateRange(row.invoice_date, range));
    const totals = Object.fromEntries(bucketKeys.map((key) => [key, 0])) as Record<string, number>;
    const counts = Object.fromEntries(bucketKeys.map((key) => [key, 0])) as Record<string, number>;
    const suppliersByBucket = Object.fromEntries(bucketKeys.map((key) => [key, new Set<number>()])) as Record<string, Set<number>>;
    const supplierMap = new Map<number, { supplier_id: number; supplier_name?: string | null; outstanding: number; invoice_count: number; overdue: number }>();
    const today = new Date().toLocaleDateString("en-CA");
    let totalOutstanding = 0;
    let overdueTotal = 0;
    let overdueCount = 0;
    let dueToday = 0;
    let weightedDays = 0;
    let weightedAmount = 0;

    for (const row of details) {
      const outstanding = Number(row.outstanding || 0);
      const days = Math.max(Number(row.days_overdue || 0), 0);
      totalOutstanding += outstanding;
      if (days > 0) {
        weightedDays += outstanding * days;
        weightedAmount += outstanding;
      }
      if ((row.aging_bucket ?? "current") !== "current") {
        overdueTotal += outstanding;
        overdueCount += 1;
      }
      if (row.due_date === today) dueToday += outstanding;
      for (const key of bucketKeys) {
        const value = Number((row as unknown as Record<string, number>)[key] || 0);
        if (value <= 0) continue;
        totals[key] += value;
        counts[key] += 1;
        suppliersByBucket[key].add(row.supplier_id);
      }
      const supplier = supplierMap.get(row.supplier_id) ?? {
        supplier_id: row.supplier_id,
        supplier_name: row.supplier_name,
        outstanding: 0,
        invoice_count: 0,
        overdue: 0,
      };
      supplier.outstanding += outstanding;
      supplier.invoice_count += 1;
      if (days > 0) supplier.overdue += outstanding;
      supplierMap.set(row.supplier_id, supplier);
    }

    return {
      ...source,
      details,
      paid,
      buckets: Object.fromEntries(bucketKeys.map((key) => [key, {
        amount: totals[key],
        invoice_count: counts[key],
        supplier_count: suppliersByBucket[key].size,
        percentage: totalOutstanding ? (totals[key] / totalOutstanding) * 100 : 0,
      }])),
      metrics: {
        ...source.metrics,
        total_outstanding: totalOutstanding,
        overdue_total: overdueTotal,
        due_today: dueToday,
        overdue_invoice_count: overdueCount,
        open_invoice_count: details.length,
        supplier_count: supplierMap.size,
        average_overdue_days: weightedAmount ? weightedDays / weightedAmount : 0,
      },
      top_suppliers: Array.from(supplierMap.values()).sort((a, b) => b.outstanding - a.outstanding).slice(0, 10),
    } as AgingResponse;
  }, [aging.data, dateFilterActive, range]);

  const paidTotal = useMemo(
    () => (agingData?.paid ?? []).reduce((sum, row) => sum + Number(row.paid_amount || 0), 0),
    [agingData],
  );
  const metrics = agingData?.metrics;

  const summaryMetrics: SummaryMetric[] = isAging
    ? [
        { label: "Total outstanding", value: money(metrics?.total_outstanding) },
        { label: "Due today", value: money(metrics?.due_today) },
        { label: "Overdue", value: money(metrics?.overdue_total) },
        { label: "Overdue invoices", value: metrics?.overdue_invoice_count ?? 0 },
        { label: "Open invoices", value: metrics?.open_invoice_count ?? 0 },
        { label: "Suppliers", value: metrics?.supplier_count ?? 0 },
      ]
    : [
        { label: "Outstanding AP", value: money(metrics?.total_outstanding) },
        { label: "Due today", value: money(metrics?.due_today) },
        { label: "Overdue", value: money(metrics?.overdue_total) },
        { label: "Open invoices", value: metrics?.open_invoice_count ?? 0 },
        { label: "Average overdue age", value: `${Number(metrics?.average_overdue_days ?? 0).toFixed(1)} days` },
        { label: "Suppliers", value: metrics?.supplier_count ?? 0 },
      ];

  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="space-y-2">
        <PageHeader
          title={isAging ? "AP Aging" : "Accounts Payable"}
          description={
            isAging
              ? "Outstanding supplier invoices grouped by how long they have been overdue."
              : "Current supplier liability, due dates, and exceptions from the AP subledger."
          }
          actions={
            isAging && agingTab === "OPEN" ? (
              <PrintPreviewButton src={printSrc} title="Account Payable Aging" ariaLabel="Print AP aging" label="Print" />
            ) : undefined
          }
        >
          <div className="mt-0.5 text-[11px] text-slate-500">
            Read-only AP subledger · aging as of today · invoice dates {dateFilterActive ? `${range.date_from || "…"} → ${range.date_to || "…"}` : "all"}
          </div>
        </PageHeader>
        <APWorkspaceHeader />

        <div className="flex flex-wrap items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 print:hidden">
          <span className="font-medium">Invoice date</span>
          <label className="inline-flex items-center gap-1">
            From
            <input
              aria-label="Invoice date from"
              className="h-8 rounded border border-slate-300 bg-white px-2"
              type="date"
              value={dateFrom}
              max={dateTo || undefined}
              onChange={(event) => setDateFrom(event.target.value)}
            />
          </label>
          <label className="inline-flex items-center gap-1">
            To
            <input
              aria-label="Invoice date to"
              className="h-8 rounded border border-slate-300 bg-white px-2"
              type="date"
              value={dateTo}
              min={dateFrom || undefined}
              onChange={(event) => setDateTo(event.target.value)}
            />
          </label>
          {dateFilterActive && (
            <Button size="sm" variant="outline" onClick={() => { setDateFrom(""); setDateTo(""); }}>Clear date filter</Button>
          )}
          {invalidRange && <span role="alert" className="text-red-700">From date must be on or before To date.</span>}
          {dateFilterActive && !invalidRange && (
            <span className="text-slate-500">Screen and print use the same invoice date range.</span>
          )}
        </div>

        {agingData?.opening_unassigned && (
          <div role="status" className="flex gap-2 rounded-md border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900">
            <AlertCircle className="mt-0.5 h-4 w-4 shrink-0" />
            The manual opening AP is recorded by account and cannot be assigned to this supplier or AP user. These balances show document activity only.
          </div>
        )}

        {!!summaryMetrics.length && <ModuleSummary metrics={summaryMetrics} />}

        {aging.isPending ? (
          <Card className="p-0"><Loading message="Loading accounts payable..." /></Card>
        ) : aging.isError ? (
          <Card className="p-0">
            <div role="alert" className="m-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-red-700">
              <div className="font-semibold">Accounts payable data could not be loaded.</div>
              <p className="mt-1 text-xs">{apiErrorMessage(aging.error, "The AP subledger did not return a usable response.")}</p>
              <Button className="mt-3" size="sm" variant="outline" onClick={() => aging.refetch()}>Try again</Button>
            </div>
          </Card>
        ) : !isAging ? (
          <>
            <Card className="overflow-hidden p-0">
              <CardHeader>
                <div>
                  <CardTitle className="text-sm">Payables Snapshot</CardTitle>
                  <CardDescription>Current supplier liability by aging bucket.</CardDescription>
                </div>
                <Link className="text-xs font-medium text-emerald-700 hover:underline" to="/accounts-payable/aging">
                  View Aging
                </Link>
              </CardHeader>
              <Table containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
                <THead>
                  <TR><TH>Bucket</TH><TH numeric>Amount</TH><TH numeric>Invoices</TH><TH numeric>Suppliers</TH></TR>
                </THead>
                <TBody>
                  {bucketKeys.map((key) => (
                    <TR key={key}>
                      <TD><Badge variant={bucketVariant(key)}>{bucketLabel[key]}</Badge></TD>
                      <TD numeric>{money(agingData?.buckets?.[key]?.amount)}</TD>
                      <TD numeric>{agingData?.buckets?.[key]?.invoice_count ?? 0}</TD>
                      <TD numeric>{agingData?.buckets?.[key]?.supplier_count ?? 0}</TD>
                    </TR>
                  ))}
                </TBody>
              </Table>
            </Card>

            <Card className="overflow-hidden p-0">
              <CardHeader>
                <div>
                  <CardTitle className="text-sm">Top Outstanding Suppliers</CardTitle>
                  <CardDescription>Suppliers with the largest open AP balance.</CardDescription>
                </div>
              </CardHeader>
              <Table containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
                <THead><TR><TH>Supplier</TH><TH numeric>Open Invoices</TH><TH numeric>Overdue</TH><TH numeric>Outstanding</TH></TR></THead>
                <TBody>
                  {(agingData?.top_suppliers ?? []).map((row, index) => (
                    <TR key={row.supplier_id}>
                      <TD><TableCellStack primary={row.supplier_name || `Supplier #${row.supplier_id}`} secondary={`#${index + 1}`} /></TD>
                      <TD numeric>{row.invoice_count}</TD>
                      <TD numeric>{money(row.overdue)}</TD>
                      <TD numeric className="font-semibold tabular-nums">{money(row.outstanding)}</TD>
                    </TR>
                  ))}
                  {!agingData?.top_suppliers?.length && (
                    <TR><TD colSpan={4} className="p-8 text-center text-slate-500">No outstanding suppliers.</TD></TR>
                  )}
                </TBody>
              </Table>
            </Card>

            <PayableTable title="Open Supplier Payables" rows={(agingData?.details ?? []).slice(0, 8)} limitNote="Showing the 8 most recent open invoices." />
          </>
        ) : (
          <>
            <div className="flex gap-5 border-b border-slate-200" role="tablist" aria-label="AP aging view">
              {(["OPEN", "PAID"] as const).map((tab) => (
                <button
                  key={tab}
                  type="button"
                  role="tab"
                  aria-selected={agingTab === tab}
                  className={`pb-2 text-sm font-medium ${
                    agingTab === tab ? "border-b-2 border-[#086B5A] text-[#086B5A]" : "text-slate-500 hover:text-slate-900"
                  }`}
                  onClick={() => setAgingTab(tab)}
                >
                  {tab === "OPEN" ? "Open / Aging" : "Paid History"}
                </button>
              ))}
            </div>

            {agingTab === "OPEN" ? (
              <>
                <Card className="overflow-hidden p-0">
                  <CardHeader>
                    <div>
                      <CardTitle className="text-sm">Aging Buckets</CardTitle>
                      <CardDescription>Outstanding AP grouped by days overdue.</CardDescription>
                    </div>
                  </CardHeader>
                  <Table containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
                    <THead><TR><TH>Bucket</TH><TH numeric>Amount</TH><TH numeric>Invoices</TH><TH numeric>Suppliers</TH><TH numeric>Share</TH></TR></THead>
                    <TBody>
                      {bucketKeys.map((key) => (
                        <TR key={key}>
                          <TD><Badge variant={bucketVariant(key)}>{bucketLabel[key]}</Badge></TD>
                          <TD numeric>{money(agingData?.buckets?.[key]?.amount)}</TD>
                          <TD numeric>{agingData?.buckets?.[key]?.invoice_count ?? 0}</TD>
                          <TD numeric>{agingData?.buckets?.[key]?.supplier_count ?? 0}</TD>
                          <TD numeric>{Number(agingData?.buckets?.[key]?.percentage ?? 0).toFixed(1)}%</TD>
                        </TR>
                      ))}
                    </TBody>
                  </Table>
                </Card>
                <PayableTable title="Open Supplier Payables" rows={agingData?.details ?? []} />
              </>
            ) : (
              <>
                <ModuleSummary
                  metrics={[
                    { label: "Total payments allocated", value: money(paidTotal) },
                    { label: "Invoices with payment", value: agingData?.paid?.length ?? 0 },
                  ]}
                />
                <PaidTable rows={agingData?.paid ?? []} />
              </>
            )}
          </>
        )}
      </div>
    </DataWorkspace>
  );
}

function PayableTable({ title, rows, limitNote }: { title: string; rows: PayableRow[]; limitNote?: string }) {
  return (
    <Card className="overflow-hidden p-0">
      <CardHeader>
        <div>
          <CardTitle className="text-sm">{title}</CardTitle>
          <CardDescription>{limitNote ?? "Outstanding invoice balances and their current aging bucket."}</CardDescription>
        </div>
        <Badge variant="outline">{rows.length} invoices</Badge>
      </CardHeader>
      {rows.length ? (
        <Table className="min-w-[800px]" containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
          <THead>
            <TR><TH>Invoice</TH><TH>Supplier</TH><TH>Due Date</TH><TH numeric>Outstanding</TH><TH>Aging</TH></TR>
          </THead>
          <TBody>
            {rows.map((row) => {
              const bucket = row.aging_bucket ?? (Number(row.over_90) > 0 ? "over_90" : Number(row["61_90"]) > 0 ? "61_90" : Number(row["31_60"]) > 0 ? "31_60" : Number(row["1_30"]) > 0 ? "1_30" : "current");
              return (
                <TR key={row.id}>
                  <TD>
                    <TableCellStack
                      primary={<InvoiceLink row={row} />}
                      secondary={row.supplier_invoice_number ? `Supplier ref: ${row.supplier_invoice_number}` : undefined}
                    />
                  </TD>
                  <TD>{row.supplier_name || `Supplier #${row.supplier_id}`}</TD>
                  <TD>{row.due_date || "—"}</TD>
                  <TD numeric className="font-semibold tabular-nums">{money(row.outstanding)}</TD>
                  <TD>
                    <Badge variant={bucketVariant(bucket)}>{bucketLabel[bucket] ?? bucket}</Badge>
                    {Number(row.days_overdue) > 0 && <div className="mt-1 text-[10px] text-slate-500">{row.days_overdue} days overdue</div>}
                  </TD>
                </TR>
              );
            })}
          </TBody>
        </Table>
      ) : (
        <Empty className="m-4" title="No outstanding supplier invoices" description="Posted invoices with an open balance will appear here." />
      )}
    </Card>
  );
}

function PaidTable({ rows }: { rows: PayableRow[] }) {
  return (
    <Card className="overflow-hidden p-0">
      <CardHeader>
        <div>
          <CardTitle className="text-sm">Invoice Payment History</CardTitle>
          <CardDescription>Payments already allocated to supplier invoices.</CardDescription>
        </div>
        <Badge variant="outline">{rows.length} invoices</Badge>
      </CardHeader>
      {rows.length ? (
        <Table className="min-w-[900px]" containerClassName="rounded-none border-x-0 border-b-0 shadow-none">
          <THead>
            <TR><TH>Invoice</TH><TH>Supplier</TH><TH>Last Payment</TH><TH numeric>Invoice Amount</TH><TH numeric>Paid</TH><TH numeric>Remaining</TH></TR>
          </THead>
          <TBody>
            {rows.map((row) => (
              <TR key={row.id}>
                <TD><InvoiceLink row={row} /></TD>
                <TD>{row.supplier_name || `Supplier #${row.supplier_id}`}</TD>
                <TD>{row.last_payment_date || "—"}</TD>
                <TD numeric>{money(row.amount)}</TD>
                <TD numeric>{money(row.paid_amount)}</TD>
                <TD numeric className="font-semibold tabular-nums">{money(row.outstanding)}</TD>
              </TR>
            ))}
          </TBody>
        </Table>
      ) : (
        <Empty className="m-4" title="No supplier invoice payments yet" description="Allocated payments will appear here once a supplier invoice is paid." />
      )}
    </Card>
  );
}
