import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useLocation } from "react-router-dom";

import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import ARWorkspaceHeader from "./ARWorkspaceHeader";
import { arReportingApi, type ARStatus, type AgingBucket } from "./reportingApi";

const money = (value: unknown) =>
  `Rp ${Number(value || 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;

const statusVariant = (status: ARStatus) =>
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

export default function ARReportingPage() {
  const location = useLocation();
  const section = location.pathname.endsWith("/detail")
    ? "detail"
    : location.pathname.endsWith("/aging")
      ? "aging"
      : "summary";
  const [page, setPage] = useState(1);
  const [searchInput, setSearchInput] = useState("");
  const [search, setSearch] = useState("");
  const pageSize = 20;

  useEffect(() => setPage(1), [section, search]);

  const summary = useQuery({
    queryKey: ["ar-reporting", "summary", page, search],
    queryFn: () => arReportingApi.summary(page, pageSize, search),
    enabled: section === "summary",
  });
  const detail = useQuery({
    queryKey: ["ar-reporting", "detail", page, search],
    queryFn: () => arReportingApi.detail(page, pageSize, search),
    enabled: section === "detail",
  });
  const aging = useQuery({
    queryKey: ["ar-reporting", "aging", page, search],
    queryFn: () => arReportingApi.aging(page, pageSize, search),
    enabled: section === "aging",
  });
  const activeQuery = section === "detail" ? detail : section === "aging" ? aging : summary;
  const data = activeQuery.data;

  return (
    <div className="space-y-5">
      <ARWorkspaceHeader />

      <Card className="p-4">
        <form
          className="flex flex-col gap-2 sm:flex-row"
          onSubmit={(event) => {
            event.preventDefault();
            setSearch(searchInput);
          }}
        >
          <input
            value={searchInput}
            onChange={(event) => setSearchInput(event.target.value)}
            placeholder="Search customer or invoice"
            className="h-9 flex-1 rounded-lg border border-slate-300 px-3 text-sm outline-none focus:border-emerald-600"
          />
          <Button type="submit" size="sm">Search</Button>
          {search && (
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => {
                setSearchInput("");
                setSearch("");
              }}
            >
              Clear
            </Button>
          )}
        </form>
      </Card>

      {section === "summary" && summary.data && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Metric label="Gross Receivables" value={money(summary.data.metrics.gross_receivables)} />
          <Metric label="Total Receipts" value={money(summary.data.metrics.total_receipts)} />
          <Metric label="Outstanding Receivables" value={money(summary.data.metrics.outstanding_receivables)} emphasis />
          <Metric label="Overdue Receivables" value={money(summary.data.metrics.overdue_receivables)} emphasis />
        </div>
      )}

      {section === "aging" && aging.data && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {(Object.keys(bucketLabels) as AgingBucket[]).map((bucket) => (
            <Metric
              key={bucket}
              label={bucketLabels[bucket]}
              value={money(aging.data.buckets[bucket].amount)}
              emphasis={bucket !== "current"}
            />
          ))}
        </div>
      )}

      {activeQuery.isError && (
        <Card className="p-5 text-center">
          <p className="text-sm text-red-600">Accounts Receivable reporting could not be loaded.</p>
          <Button className="mt-3" variant="outline" size="sm" onClick={() => activeQuery.refetch()}>
            Try Again
          </Button>
        </Card>
      )}
      {activeQuery.isLoading && (
        <Card className="p-8 text-center text-sm text-slate-500">
          Loading Accounts Receivable report…
        </Card>
      )}

      {!activeQuery.isLoading && !activeQuery.isError && section === "summary" && summary.data && (
        <Card className="p-0">
          <Title title="Receivables by Customer" subtitle="Customer balances from the Accounts Receivable subledger." />
          <div className="overflow-x-auto">
            <Table variant="standard">
              <THead><TR><TH>Customer</TH><TH className="text-right">Gross</TH><TH className="text-right">Receipts</TH><TH className="text-right">Outstanding</TH><TH className="text-right">Overdue Invoices</TH><TH>Status</TH></TR></THead>
              <TBody>
                {summary.data.items.map((row) => (
                  <TR key={row.customer_id}>
                    <TD><div className="font-medium">{row.customer_name || `Customer #${row.customer_id}`}</div><div className="text-[10px] text-slate-500">{row.customer_code || "—"} · {row.invoice_count} invoices</div></TD>
                    <TD className="text-right">{money(row.gross_amount)}</TD>
                    <TD className="text-right">{money(row.received_amount)}</TD>
                    <TD className="text-right font-semibold">{money(row.outstanding_amount)}</TD>
                    <TD className="text-right">{row.overdue_invoice_count}</TD>
                    <TD><Badge variant={statusVariant(row.status)}>{statusLabel[row.status]}</Badge></TD>
                  </TR>
                ))}
                {!detail.data.items.length && <TR><TD colSpan={6} className="py-10 text-center text-slate-500">No receivables found.</TD></TR>}
              </TBody>
            </Table>
          </div>
        </Card>
      )}

      {!activeQuery.isLoading && !activeQuery.isError && section === "detail" && detail.data && (
        <Card className="p-0">
          <Title title="Receivables Detail" subtitle="Invoice-level customer balances and collection status." />
          <div className="overflow-x-auto">
            <Table variant="standard">
              <THead><TR><TH>Date</TH><TH>Invoice</TH><TH>Customer</TH><TH>Due Date</TH><TH className="text-right">Gross</TH><TH className="text-right">Receipts</TH><TH className="text-right">Outstanding</TH><TH>Status</TH></TR></THead>
              <TBody>
                {aging.data.items.map((row) => (
                  <TR key={row.invoice_id}>
                    <TD>{row.invoice_date}</TD>
                    <TD className="font-medium">{row.invoice_number}</TD>
                    <TD>{row.customer_name || `Customer #${row.customer_id}`}</TD>
                    <TD>{row.due_date || "—"}</TD>
                    <TD className="text-right">{money(row.gross_amount)}</TD>
                    <TD className="text-right">{money(row.received_amount)}</TD>
                    <TD className="text-right font-semibold">{money(row.outstanding_amount)}</TD>
                    <TD><Badge variant={statusVariant(row.status)}>{statusLabel[row.status]}</Badge></TD>
                  </TR>
                ))}
                {!summary.data.items.length && <TR><TD colSpan={8} className="py-10 text-center text-slate-500">No receivable invoices found.</TD></TR>}
              </TBody>
            </Table>
          </div>
        </Card>
      )}

      {!activeQuery.isLoading && !activeQuery.isError && section === "aging" && aging.data && (
        <Card className="p-0">
          <Title title="AR Aging" subtitle={`Outstanding customer balances as of ${aging.data.as_of_date}.`} />
          <div className="overflow-x-auto">
            <Table variant="standard">
              <THead><TR><TH>Customer</TH>{(Object.keys(bucketLabels) as AgingBucket[]).map((bucket) => <TH key={bucket} className="text-right">{bucketLabels[bucket]}</TH>)}<TH className="text-right">Outstanding</TH></TR></THead>
              <TBody>
                {detail.data.items.map((row) => (
                  <TR key={row.customer_id}>
                    <TD><div className="font-medium">{row.customer_name || `Customer #${row.customer_id}`}</div><div className="text-[10px] text-slate-500">{row.customer_code || "—"}</div></TD>
                    {(Object.keys(bucketLabels) as AgingBucket[]).map((bucket) => <TD key={bucket} className="text-right">{money(row[bucket])}</TD>)}
                    <TD className="text-right font-semibold">{money(row.outstanding_amount)}</TD>
                  </TR>
                ))}
                {!aging.data.items.length && <TR><TD colSpan={7} className="py-10 text-center text-slate-500">No outstanding receivables.</TD></TR>}
              </TBody>
            </Table>
          </div>
        </Card>
      )}

      {data && data.total_pages > 1 && (
        <div className="flex items-center justify-end gap-2">
          <Button variant="outline" size="sm" disabled={!data.has_previous} onClick={() => setPage((value) => Math.max(1, value - 1))}>Previous</Button>
          <span className="text-xs text-slate-500">Page {data.page} of {data.total_pages}</span>
          <Button variant="outline" size="sm" disabled={!data.has_next} onClick={() => setPage((value) => value + 1)}>Next</Button>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, emphasis = false }: { label: string; value: string; emphasis?: boolean }) {
  return <Card className="p-4"><div className="text-xs uppercase tracking-wide text-slate-500">{label}</div><div className={`mt-2 text-xl font-semibold ${emphasis ? "text-red-700" : ""}`}>{value}</div></Card>;
}

function Title({ title, subtitle }: { title: string; subtitle: string }) {
  return <div className="border-b px-4 py-3"><h2 className="font-semibold">{title}</h2><p className="text-xs text-slate-500">{subtitle}</p></div>;
}
