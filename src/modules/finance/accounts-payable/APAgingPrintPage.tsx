import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import Loading from "@/components/ui/Loading";

const money = (value: unknown) => Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function APAgingPrintPage() {
  const query = useQuery({
    queryKey: ["accounts-payable-aging", "print"],
    queryFn: async () => (await api.get("/ap-aging/print")).data,
  });

  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>AP aging report could not be loaded.</p>;
  const data = query.data as any;
  const rows = data.rows ?? [];
  const totals = data.totals ?? {};

  return (
    <article className="mx-auto bg-white p-6 text-[10px] text-slate-950 print:p-0">
      <style>{`@page{size:landscape;margin:10mm} @media print{body{background:#fff}.app-shell,.sidebar,.topbar{display:none!important}}`}</style>
      <header className="mb-4 text-center">
        <h1 className="text-lg font-bold tracking-wide">ACCOUNT PAYABLE AGING</h1>
        <div className="mt-1 text-xs">Hotel Mutiara Merdeka Pekanbaru</div>
        <div className="mt-1">As of {data.as_of_date}</div>
      </header>

      <table className="w-full border-collapse">
        <thead>
          <tr>
            {[
              "No.", "Code", "Supplier", "Purchase", "Payment", "0 - 30 Days",
              "31 - 60 Days", "61 - 90 Days", "91 - 120 Days", "Over 120 Days", "Total",
            ].map((label) => <th key={label} className="border border-slate-700 px-2 py-1.5 text-left font-semibold">{label}</th>)}
          </tr>
        </thead>
        <tbody>
          {rows.map((row: any, index: number) => (
            <tr key={row.supplier_id}>
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
            </tr>
          ))}
        </tbody>
        <tfoot>
          <tr className="font-bold">
            <td colSpan={3} className="border border-slate-700 px-2 py-2 text-right">TOTAL</td>
            <td className="border border-slate-700 px-2 py-2 text-right">{money(totals.purchase)}</td>
            <td className="border border-slate-700 px-2 py-2 text-right">{money(totals.payment)}</td>
            <td className="border border-slate-700 px-2 py-2 text-right">{money(totals["0_30"])}</td>
            <td className="border border-slate-700 px-2 py-2 text-right">{money(totals["31_60"])}</td>
            <td className="border border-slate-700 px-2 py-2 text-right">{money(totals["61_90"])}</td>
            <td className="border border-slate-700 px-2 py-2 text-right">{money(totals["91_120"])}</td>
            <td className="border border-slate-700 px-2 py-2 text-right">{money(totals.over_120)}</td>
            <td className="border border-slate-700 px-2 py-2 text-right">{money(totals.outstanding)}</td>
          </tr>
        </tfoot>
      </table>

      <footer className="mt-4 flex justify-between text-[9px] text-slate-600">
        <span>Printed by {data.generated_by_name || "Finance"}</span>
        <span>{data.generated_at ? new Date(data.generated_at).toLocaleString() : ""}</span>
      </footer>
    </article>
  );
}
