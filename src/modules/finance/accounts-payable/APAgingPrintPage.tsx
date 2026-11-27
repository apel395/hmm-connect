import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import api from "@/api/client";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import { apiErrorMessage } from "@/utils/apiError";
import { agingDateRangeFromSearch, inAgingDateRange } from "./agingFilters";

type AgingAmount = string | number | null | undefined;

type AgingPrintRow = {
  supplier_id: number | string;
  supplier_code?: string | null;
  supplier_name?: string | null;
  purchase?: AgingAmount;
  payment?: AgingAmount;
  "0_30"?: AgingAmount;
  "31_60"?: AgingAmount;
  "61_90"?: AgingAmount;
  "91_120"?: AgingAmount;
  over_120?: AgingAmount;
  outstanding?: AgingAmount;
};

type AgingPrintTotals = {
  purchase?: AgingAmount;
  payment?: AgingAmount;
  "0_30"?: AgingAmount;
  "31_60"?: AgingAmount;
  "61_90"?: AgingAmount;
  "91_120"?: AgingAmount;
  over_120?: AgingAmount;
  outstanding?: AgingAmount;
};

type AgingPrintResponse = {
  as_of_date?: string | null;
  rows?: AgingPrintRow[];
  totals?: AgingPrintTotals;
  printed_by?: string | null;
  generated_at?: string | null;
};

type AgingInvoice = {
  id: number;
  supplier_id: number;
  supplier_name?: string | null;
  invoice_date?: string | null;
  due_date?: string | null;
  amount?: AgingAmount;
  paid_amount?: AgingAmount;
  outstanding?: AgingAmount;
};

const PRINT_BUCKETS = ["0_30", "31_60", "61_90", "91_120", "over_120"] as const;

const printBucket = (days: number) => {
  if (days <= 30) return "0_30";
  if (days <= 60) return "31_60";
  if (days <= 90) return "61_90";
  if (days <= 120) return "91_120";
  return "over_120";
};

const money = (value: AgingAmount) =>
  Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function APAgingPrintPage() {
  const [searchParams] = useSearchParams();
  const dateFrom = searchParams.get("date_from") || "";
  const dateTo = searchParams.get("date_to") || "";
  const invalidRange = Boolean(dateFrom && dateTo && dateFrom > dateTo);
  const dateFilterActive = Boolean(dateFrom || dateTo) && !invalidRange;
  const range = useMemo(() => agingDateRangeFromSearch(searchParams), [searchParams]);

  const query = useQuery({
    queryKey: ["accounts-payable-aging", "print"],
    queryFn: async () => (await api.get<AgingPrintResponse>("/ap-aging/print")).data,
  });
  const invoices = useQuery({
    queryKey: ["accounts-payable-aging", "print", "filtered", dateFrom, dateTo],
    queryFn: async () => (await api.get<{ details: AgingInvoice[] }>("/ap-aging")).data.details,
    enabled: dateFilterActive,
  });

  const { rows, totals } = useMemo(() => {
    if (!dateFilterActive) return { rows: query.data?.rows ?? [], totals: query.data?.totals ?? {} };
    const supplierCodes = new Map((query.data?.rows ?? []).map((row) => [Number(row.supplier_id), row.supplier_code]));
    const grouped = new Map<number, AgingPrintRow>();
    const today = new Date().toLocaleDateString("en-CA");
    for (const invoice of invoices.data ?? []) {
      if (!inAgingDateRange(invoice.invoice_date, range)) continue;
      const key = Number(invoice.supplier_id);
      const bucket = printBucket(invoice.due_date ? Math.max((new Date(today).getTime() - new Date(invoice.due_date).getTime()) / 86400000, 0) : 0);
      const row = grouped.get(key) ?? {
        supplier_id: key,
        supplier_code: supplierCodes.get(key),
        supplier_name: invoice.supplier_name,
        purchase: 0,
        payment: 0,
        outstanding: 0,
        ...Object.fromEntries(PRINT_BUCKETS.map((item) => [item, 0])),
      };
      const outstanding = Number(invoice.outstanding || 0);
      row.purchase = Number(row.purchase || 0) + Number(invoice.amount || 0);
      row.payment = Number(row.payment || 0) + Number(invoice.paid_amount || 0);
      row.outstanding = Number(row.outstanding || 0) + outstanding;
      row[bucket] = Number(row[bucket] || 0) + outstanding;
      grouped.set(key, row);
    }
    const filteredRows = Array.from(grouped.values()).sort((a, b) => String(a.supplier_name || "").localeCompare(String(b.supplier_name || "")));
    const filteredTotals = Object.fromEntries(
      (["purchase", "payment", "outstanding", ...PRINT_BUCKETS] as const).map((key) => [
        key,
        filteredRows.reduce((sum, row) => sum + Number(row[key] || 0), 0),
      ]),
    ) as AgingPrintTotals;
    return { rows: filteredRows, totals: filteredTotals };
  }, [dateFilterActive, invoices.data, query.data, range]);

  if (query.isLoading || (dateFilterActive && invoices.isLoading)) {
    return <div data-print-ready="false"><Loading message="Loading AP aging report…" /></div>;
  }
  if (query.isError || (dateFilterActive && invoices.isError)) {
    return (
      <div data-print-ready="false" role="alert" className="p-6 text-sm text-red-700">
        {apiErrorMessage(query.error || invoices.error, "AP aging report could not be loaded.")}
      </div>
    );
  }
  if (!query.data || (dateFilterActive && !invoices.data)) {
    return <div data-print-ready="false" role="alert" className="p-6 text-sm text-red-700">AP aging report could not be loaded.</div>;
  }

  const { as_of_date, printed_by, generated_at } = query.data;

  if (!rows.length) {
    return (
      <div data-print-ready="true">
        <Empty title="No AP aging rows" description="There are no open supplier invoices to print for this report." />
      </div>
    );
  }

  return (
    <article data-print-ready="true" className="mx-auto bg-white p-6 text-[10px] text-slate-950 print:p-0">
      <style>{`@page{size:landscape;margin:10mm} @media print{body{background:#fff}.app-shell,.sidebar,.topbar{display:none!important}}`}</style>
      <header className="mb-4 border-b-2 border-slate-800 pb-3">
        <div className="grid grid-cols-[90px_1fr_90px] items-center">
          <img src="/logoprint.jpeg" alt="PT. Mutiara Merdeka Hotel" className="h-12 w-auto object-contain" />
          <div className="text-center"><h1 className="text-lg font-bold tracking-wide">ACCOUNT PAYABLE AGING</h1><div className="mt-1 text-xs">Hotel Mutiara Merdeka Pekanbaru</div></div>
          <div />
        </div>
        <div className="mt-1">As of {as_of_date}</div>
        {dateFilterActive && <div className="mt-0.5">Invoice date {dateFrom || "…"} to {dateTo || "…"}</div>}
      </header>

      <table className="w-full border-collapse">
        <thead><tr>{[
          "No.", "Code", "Supplier", "Purchase", "Payment", "0 - 30 Days",
          "31 - 60 Days", "61 - 90 Days", "91 - 120 Days", "Over 120 Days", "Total",
        ].map((label) => <th key={label} className="border border-slate-700 px-2 py-1.5 text-left font-semibold">{label}</th>)}</tr></thead>
        <tbody>{rows.map((row, index) => <tr key={row.supplier_id}>
          <td className="border border-slate-500 px-2 py-1 text-right">{index + 1}</td>
          <td className="border border-slate-500 px-2 py-1">{row.supplier_code || `S${row.supplier_id}`}</td>
          <td className="border border-slate-500 px-2 py-1">{row.supplier_name || `Supplier #${row.supplier_id}`}</td>
          <td className="border border-slate-500 px-2 py-1 text-right tabular-nums">{money(row.purchase)}</td>
          <td className="border border-slate-500 px-2 py-1 text-right tabular-nums">{money(row.payment)}</td>
          <td className="border border-slate-500 px-2 py-1 text-right tabular-nums">{money(row["0_30"])}</td>
          <td className="border border-slate-500 px-2 py-1 text-right tabular-nums">{money(row["31_60"])}</td>
          <td className="border border-slate-500 px-2 py-1 text-right tabular-nums">{money(row["61_90"])}</td>
          <td className="border border-slate-500 px-2 py-1 text-right tabular-nums">{money(row["91_120"])}</td>
          <td className="border border-slate-500 px-2 py-1 text-right tabular-nums">{money(row.over_120)}</td>
          <td className="border border-slate-500 px-2 py-1 text-right font-semibold tabular-nums">{money(row.outstanding)}</td>
        </tr>)}</tbody>
        <tfoot><tr className="font-bold">
          <td colSpan={3} className="border border-slate-700 px-2 py-2 text-right">TOTAL</td>
          <td className="border border-slate-700 px-2 py-2 text-right">{money(totals.purchase)}</td>
          <td className="border border-slate-700 px-2 py-2 text-right">{money(totals.payment)}</td>
          <td className="border border-slate-700 px-2 py-2 text-right">{money(totals["0_30"])}</td>
          <td className="border border-slate-700 px-2 py-2 text-right">{money(totals["31_60"])}</td>
          <td className="border border-slate-700 px-2 py-2 text-right">{money(totals["61_90"])}</td>
          <td className="border border-slate-700 px-2 py-2 text-right">{money(totals["91_120"])}</td>
          <td className="border border-slate-700 px-2 py-2 text-right">{money(totals.over_120)}</td>
          <td className="border border-slate-700 px-2 py-2 text-right">{money(totals.outstanding)}</td>
        </tr></tfoot>
      </table>

      <footer className="mt-4 flex justify-between text-[9px] text-slate-600">
        <span>Printed by {printed_by || "Finance"}</span>
        <span>{generated_at ? new Date(generated_at).toLocaleString() : ""}</span>
      </footer>
    </article>
  );
}
