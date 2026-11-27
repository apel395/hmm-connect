import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import { apiErrorMessage } from "@/utils/apiError";

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

const money = (value: AgingAmount) =>
  Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function APAgingPrintPage() {
  const query = useQuery({
    queryKey: ["accounts-payable-aging", "print"],
    queryFn: async () => (await api.get<AgingPrintResponse>("/ap-aging/print")).data,
  });

  if (query.isLoading) {
    return <div data-print-ready="false"><Loading message="Loading AP aging report…" /></div>;
  }
  if (query.isError) {
    return (
      <div data-print-ready="false" role="alert" className="p-6 text-sm text-red-700">
        {apiErrorMessage(query.error, "AP aging report could not be loaded.")}
      </div>
    );
  }
  if (!query.data) {
    return <div data-print-ready="false" role="alert" className="p-6 text-sm text-red-700">AP aging report could not be loaded.</div>;
  }

  const { as_of_date, printed_by, generated_at } = query.data;
  const rows = query.data.rows ?? [];
  const totals = query.data.totals ?? {};

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
