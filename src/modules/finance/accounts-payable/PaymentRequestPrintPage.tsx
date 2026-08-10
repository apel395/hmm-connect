import { useQuery } from "@tanstack/react-query";
import api from "@/api/client";
import Loading from "@/components/ui/Loading";

const money = (value: unknown) => Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const date = (value: unknown) => value ? new Date(String(value)).toLocaleDateString("id-ID") : "—";

export default function PaymentRequestPrintPage() {
  const query = useQuery({
    queryKey: ["accounts-payable-aging", "payment-request-print"],
    queryFn: async () => (await api.get("/ap-aging")).data,
  });

  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>Payment request could not be loaded.</p>;

  const rows = (query.data.details ?? []).filter((row: any) => Number(row.outstanding || 0) > 0);
  const totalInvoice = rows.reduce((sum: number, row: any) => sum + Number(row.amount || 0), 0);
  const totalPaid = rows.reduce((sum: number, row: any) => sum + Number(row.paid_amount || 0), 0);
  const totalRequest = rows.reduce((sum: number, row: any) => sum + Number(row.outstanding || 0), 0);
  const now = new Date();

  return (
    <article className="mx-auto bg-white p-6 text-[10px] text-slate-950 print:p-0">
      <style>{`@page{size:landscape;margin:10mm} @media print{body{background:#fff}.app-shell,.sidebar,.topbar{display:none!important}}`}</style>
      <header className="mb-4 text-center">
        <h1 className="text-lg font-bold tracking-wide">PAYMENT REQUEST</h1>
        <div className="mt-1 text-xs">Hotel Mutiara Merdeka Pekanbaru</div>
        <div className="mt-1">Outstanding Supplier Invoices as of {now.toLocaleDateString("id-ID")}</div>
      </header>

      <table className="w-full border-collapse">
        <thead><tr>{["No.", "Supplier", "Internal Invoice", "Supplier Invoice", "Invoice Date", "Due Date", "Invoice Amount", "Paid", "Requested Payment"].map((label) => <th key={label} className="border border-slate-700 px-2 py-1.5 text-left font-semibold">{label}</th>)}</tr></thead>
        <tbody>
          {rows.map((row: any, index: number) => <tr key={row.id}><td className="border border-slate-500 px-2 py-1 text-right">{index + 1}</td><td className="border border-slate-500 px-2 py-1">{row.supplier_name || `Supplier #${row.supplier_id}`}</td><td className="border border-slate-500 px-2 py-1">{row.invoice_number || "—"}</td><td className="border border-slate-500 px-2 py-1">{row.supplier_invoice_number || "—"}</td><td className="border border-slate-500 px-2 py-1">{date(row.invoice_date)}</td><td className="border border-slate-500 px-2 py-1">{date(row.due_date)}</td><td className="border border-slate-500 px-2 py-1 text-right tabular-nums">{money(row.amount)}</td><td className="border border-slate-500 px-2 py-1 text-right tabular-nums">{money(row.paid_amount)}</td><td className="border border-slate-500 px-2 py-1 text-right font-semibold tabular-nums">{money(row.outstanding)}</td></tr>)}
          {!rows.length && <tr><td colSpan={9} className="border border-slate-500 px-2 py-6 text-center text-slate-500">No outstanding supplier invoices.</td></tr>}
        </tbody>
        <tfoot><tr className="font-bold"><td colSpan={6} className="border border-slate-700 px-2 py-2 text-right">TOTAL</td><td className="border border-slate-700 px-2 py-2 text-right">{money(totalInvoice)}</td><td className="border border-slate-700 px-2 py-2 text-right">{money(totalPaid)}</td><td className="border border-slate-700 px-2 py-2 text-right">{money(totalRequest)}</td></tr></tfoot>
      </table>

      <section className="mt-12 grid grid-cols-3 gap-16 text-center">{["Prepared By", "Checked By", "Approved By"].map((label) => <div key={label}><div className="mb-14">{label}</div><div className="border-t border-slate-800 pt-1">Name / Signature</div></div>)}</section>
      <footer className="mt-8 flex justify-between text-[9px] text-slate-600"><span>Payment request generated from posted outstanding supplier invoices.</span><span>Printed {now.toLocaleString("id-ID")}</span></footer>
    </article>
  );
}
