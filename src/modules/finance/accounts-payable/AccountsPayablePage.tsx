import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AlertCircle, FileText, WalletCards } from "lucide-react";
import PageHeader from "@/components/common/PageHeader";
import Card from "@/components/ui/Card";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import { Table, TBody, TD, TH, THead, TR } from "@/components/ui/Table";
import api from "@/api/interceptor";

type AgingDetail = {
  invoice_number: string | null;
  supplier_id: number;
  due_date: string | null;
  outstanding: number | string;
  current: number | string;
  "1_30": number | string;
  "31_60": number | string;
  "61_90": number | string;
  over_90: number | string;
};

type AgingResponse = {
  summary: {
    current: number | string;
    "1_30": number | string;
    "31_60": number | string;
    "61_90": number | string;
    over_90: number | string;
  };
  details: AgingDetail[];
};

const money = (value: unknown) =>
  `Rp ${Number(value || 0).toLocaleString("id-ID", { maximumFractionDigits: 0 })}`;

export default function AccountsPayablePage() {
  const aging = useQuery({
    queryKey: ["accounts-payable-aging"],
    queryFn: async () => (await api.get<AgingResponse>("/api/v1/ap-aging")).data,
  });

  const totalOutstanding = useMemo(() => {
    const summary = aging.data?.summary;
    if (!summary) return 0;
    return Number(summary.current || 0) + Number(summary["1_30"] || 0) +
      Number(summary["31_60"] || 0) + Number(summary["61_90"] || 0) +
      Number(summary.over_90 || 0);
  }, [aging.data]);

  const overdue = useMemo(() => {
    const summary = aging.data?.summary;
    if (!summary) return 0;
    return Number(summary["1_30"] || 0) + Number(summary["31_60"] || 0) +
      Number(summary["61_90"] || 0) + Number(summary.over_90 || 0);
  }, [aging.data]);

  return (
    <div className="space-y-5">
      <PageHeader
        title="Accounts Payable"
        description="Monitor supplier obligations, due dates, aging, and invoice settlement status."
        actions={
          <div className="flex gap-2">
            <Link to="/supplier-invoices">
              <Button variant="outline"><FileText className="h-4 w-4" /> Supplier Invoices</Button>
            </Link>
            <Link to="/payments">
              <Button><WalletCards className="h-4 w-4" /> Record Payment</Button>
            </Link>
          </div>
        }
      />

      <div className="grid gap-3 md:grid-cols-3">
        <Card className="p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500">Outstanding Payables</div>
          <div className="mt-2 text-2xl font-semibold">{money(totalOutstanding)}</div>
          <div className="mt-1 text-xs text-slate-500">All unpaid supplier obligations</div>
        </Card>
        <Card className="p-4">
          <div className="text-xs uppercase tracking-wide text-slate-500">Current</div>
          <div className="mt-2 text-2xl font-semibold">{money(aging.data?.summary.current)}</div>
          <div className="mt-1 text-xs text-slate-500">Not yet overdue</div>
        </Card>
        <Card className="p-4">
          <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-slate-500">
            <AlertCircle className="h-4 w-4 text-amber-600" /> Overdue
          </div>
          <div className="mt-2 text-2xl font-semibold">{money(overdue)}</div>
          <div className="mt-1 text-xs text-slate-500">Past supplier due dates</div>
        </Card>
      </div>

      <Card className="p-4">
        <h2 className="mb-3 text-base font-semibold">Aging Summary</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[
            ["Current", aging.data?.summary.current],
            ["1–30 Days", aging.data?.summary["1_30"]],
            ["31–60 Days", aging.data?.summary["31_60"]],
            ["61–90 Days", aging.data?.summary["61_90"]],
            ["Over 90 Days", aging.data?.summary.over_90],
          ].map(([label, value]) => (
            <div key={String(label)} className="rounded-lg border border-slate-200 bg-slate-50 p-3">
              <div className="text-xs text-slate-500">{label}</div>
              <div className="mt-1 font-semibold">{money(value)}</div>
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-0">
        <div className="border-b border-slate-200 px-4 py-3">
          <h2 className="font-semibold">Open Supplier Payables</h2>
        </div>
        {aging.isLoading ? (
          <p className="py-10 text-center text-sm text-slate-500">Loading accounts payable…</p>
        ) : aging.isError ? (
          <div className="p-6 text-center">
            <p className="text-sm text-red-600">Accounts payable data could not be loaded.</p>
            <Button className="mt-3" size="sm" variant="outline" onClick={() => aging.refetch()}>Try Again</Button>
          </div>
        ) : !aging.data?.details.length ? (
          <p className="py-10 text-center text-sm text-slate-500">No outstanding supplier payables.</p>
        ) : (
          <div className="overflow-x-auto">
            <Table variant="standard">
              <THead><TR><TH>Invoice</TH><TH>Supplier</TH><TH>Due Date</TH><TH className="text-right">Outstanding</TH><TH>Aging</TH></TR></THead>
              <TBody>
                {aging.data.details.map((row, index) => {
                  const bucket = Number(row.over_90) > 0 ? "Over 90" : Number(row["61_90"]) > 0 ? "61–90" : Number(row["31_60"]) > 0 ? "31–60" : Number(row["1_30"]) > 0 ? "1–30" : "Current";
                  return <TR key={`${row.invoice_number ?? "invoice"}-${index}`}>
                    <TD className="font-medium">{row.invoice_number || "—"}</TD>
                    <TD>Supplier #{row.supplier_id}</TD>
                    <TD>{row.due_date || "—"}</TD>
                    <TD className="text-right tabular-nums">{money(row.outstanding)}</TD>
                    <TD><Badge variant={bucket === "Current" ? "success" : bucket === "Over 90" ? "danger" : "warning"}>{bucket}</Badge></TD>
                  </TR>;
                })}
              </TBody>
            </Table>
          </div>
        )}
      </Card>

      <Card className="border-emerald-200 bg-emerald-50/60 p-4">
        <h3 className="font-semibold text-emerald-900">Direct Use flow</h3>
        <p className="mt-1 text-sm text-emerald-800">
          Direct-use purchases should be charged to the selected expense or cost account instead of increasing inventory. After the supplier invoice is verified, the amount becomes Accounts Payable until payment is posted.
        </p>
      </Card>
    </div>
  );
}
