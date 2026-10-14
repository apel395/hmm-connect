import ReportUnitButtons from "@/components/reports/ReportUnitButtons";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useLocation } from "react-router-dom";

import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import APWorkspaceHeader from "./APWorkspaceHeader";
import { apReportingApi, type APStatus } from "./reportingApi";

const money = (value: unknown) =>
  `Rp ${Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

const statusVariant = (status: APStatus) =>
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
  const [unit,setUnit]=useState("");
  const pageSize = 20;

  const summary = useQuery({
    queryKey: ["ap-reporting", "summary", page,unit],
    queryFn: () => apReportingApi.summary(page, pageSize,Number(unit)||undefined),
    enabled: !isDetail,
  });
  const detail = useQuery({
    queryKey: ["ap-reporting", "detail", page,unit],
    queryFn: () => apReportingApi.detail(page, pageSize,Number(unit)||undefined),
    enabled: isDetail,
  });

  const loading = isDetail ? detail.isLoading : summary.isLoading;
  const error = isDetail ? detail.isError : summary.isError;
  const data = isDetail ? detail.data : summary.data;

  useEffect(() => setPage(1), [isDetail]);

  return (
    <div className="space-y-5">
      <APWorkspaceHeader />
      <ReportUnitButtons value={unit} onChange={id=>{setUnit(id);setPage(1);}}/>

      {!isDetail && summary.data && (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Metric label="Gross Payables" value={money(summary.data.metrics.gross_payables)} />
            <Metric label="Total Payments" value={money(summary.data.metrics.total_payments)} />
            <Metric label="Outstanding Payables" value={money(summary.data.metrics.outstanding_payables)} emphasis />
            <Metric label="Suppliers" value={String(summary.data.metrics.supplier_count)} />
          </div>

          <div className="grid gap-3 md:grid-cols-3">
            <StatusCard label="Paid" count={summary.data.status_counts.PAID} />
            <StatusCard label="Partially Paid" count={summary.data.status_counts.PARTIALLY_PAID} />
            <StatusCard label="Unpaid" count={summary.data.status_counts.UNPAID} />
          </div>
        </>
      )}

      {error && (
        <Card className="p-5 text-center">
          <p className="text-sm text-red-600">Accounts Payable reporting could not be loaded.</p>
          <Button
            className="mt-3"
            variant="outline"
            size="sm"
            onClick={() => (isDetail ? detail.refetch() : summary.refetch())}
          >
            Try Again
          </Button>
        </Card>
      )}
      {loading && <Card className="p-8 text-center text-sm text-slate-500">Loading Accounts Payable report…</Card>}

      {!loading && !error && !isDetail && summary.data && (
        <Card className="p-0">
          <div className="border-b px-4 py-3">
            <h2 className="font-semibold">Payables by Supplier</h2>
            <p className="text-xs text-slate-500">Posted supplier invoices summarized by supplier.</p>
          </div>
          <div className="overflow-x-auto">
            <Table variant="standard">
              <THead><TR><TH>Supplier</TH><TH className="text-right">Gross Payables</TH><TH className="text-right">Payments</TH><TH className="text-right">Adjustments</TH><TH className="text-right">Outstanding</TH><TH>Status</TH></TR></THead>
              <TBody>
                {summary.data.items.map((row) => (
                  <TR key={row.supplier_id}>
                    <TD><div className="font-medium">{row.supplier_name || `Supplier #${row.supplier_id}`}</div><div className="text-[10px] text-slate-500">{row.supplier_code || "—"} · {row.invoice_count} invoices</div></TD>
                    <TD className="text-right">{money(row.gross_amount)}</TD>
                    <TD className="text-right">{money(row.paid_amount)}</TD>
                    <TD className="text-right">{money(row.adjustment_amount)}</TD>
                    <TD className="text-right font-semibold">{money(row.outstanding_amount)}</TD>
                    <TD><Badge variant={statusVariant(row.status)}>{statusLabel[row.status]}</Badge></TD>
                  </TR>
                ))}
                {!summary.data.items.length && <TR><TD colSpan={6} className="py-10 text-center text-slate-500">No posted supplier invoices.</TD></TR>}
              </TBody>
            </Table>
          </div>
        </Card>
      )}

      {!loading && !error && isDetail && detail.data && (
        <Card className="p-0">
          <div className="border-b px-4 py-3">
            <h2 className="font-semibold">Payables Detail</h2>
            <p className="text-xs text-slate-500">Invoice-level liability and payment history.</p>
          </div>
          <div className="overflow-x-auto">
            <Table variant="standard">
              <THead><TR><TH>Date</TH><TH>Invoice</TH><TH>Supplier</TH><TH>Due Date</TH><TH className="text-right">Gross</TH><TH className="text-right">Payments</TH><TH className="text-right">Adjustments</TH><TH className="text-right">Outstanding</TH><TH>Status</TH></TR></THead>
              <TBody>
                {detail.data.items.map((row) => (
                  <TR key={row.invoice_id}>
                    <TD>{row.invoice_date}</TD>
                    <TD><Link className="font-medium text-emerald-700 hover:underline" to={`/supplier-invoices/${row.invoice_id}`}>{row.invoice_number}</Link><div className="text-[10px] text-slate-500">Supplier ref: {row.supplier_invoice_number}</div></TD>
                    <TD>{row.supplier_name || `Supplier #${row.supplier_id}`}</TD>
                    <TD>{row.due_date || "—"}</TD>
                    <TD className="text-right">{money(row.gross_amount)}</TD>
                    <TD className="text-right">{money(row.paid_amount)}</TD>
                    <TD className="text-right">{money(row.adjustment_amount)}</TD>
                    <TD className="text-right font-semibold">{money(row.outstanding_amount)}</TD>
                    <TD><Badge variant={statusVariant(row.status)}>{statusLabel[row.status]}</Badge></TD>
                  </TR>
                ))}
                {!detail.data.items.length && <TR><TD colSpan={9} className="py-10 text-center text-slate-500">No posted supplier invoices.</TD></TR>}
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

function StatusCard({ label, count }: { label: string; count: number }) {
  return <Card className="p-4"><div className="text-xs text-slate-500">{label}</div><div className="mt-1 text-2xl font-semibold">{count}</div></Card>;
}
