import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import Loading from "@/components/ui/Loading";
import { getLedgerPrint } from "./api";

const money = (value: unknown) => Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const dateLabel = (value: string) => (value ? new Date(value).toLocaleDateString("en-GB") : value);

export default function GeneralLedgerPrintPage() {
  const [searchParams] = useSearchParams();
  const params = Object.fromEntries(
    Object.entries({
      search: searchParams.get("search") || "",
      account_id: searchParams.get("account_id") || "",
      date_from: searchParams.get("date_from") || "",
      date_to: searchParams.get("date_to") || "",
      reference_type: searchParams.get("reference_type") || "",
      supplier_id: searchParams.get("supplier_id") || "",
      department_id: searchParams.get("department_id") || "",
      location_id: searchParams.get("location_id") || "",
      business_unit_id: searchParams.get("business_unit_id") || "",
    }).filter(([, value]) => value !== ""),
  );
  const query = useQuery({
    queryKey: ["general-ledger", "print", params],
    queryFn: () => getLedgerPrint(params),
  });

  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>General ledger could not be loaded.</p>;
  const data = query.data as any;
  const rows = data.items ?? [];
  const labels: Array<[keyof typeof params, string]> = [
    ["account_id", "Account"],
    ["supplier_id", "Supplier"],
    ["department_id", "Department"],
    ["location_id", "Location"],
    ["business_unit_id", "Business Unit"],
    ["reference_type", "Document Type"],
  ];
  const context = labels.filter(([key]) => params[key]).map(([key, label]) => `${label}: ${params[key]}`);
  const period = params.date_from || params.date_to
    ? `${params.date_from ? dateLabel(params.date_from) : "…"} – ${params.date_to ? dateLabel(params.date_to) : "…"}`
    : "All time";

  return (
    <article className="mx-auto bg-white p-6 text-[10px] text-slate-950 print:p-0">
      <style>{`@page{size:landscape;margin:10mm} @media print{body{background:#fff}.app-shell,.sidebar,.topbar{display:none!important}}`}</style>
      <header className="mb-4 text-center">
        <h1 className="text-lg font-bold tracking-wide">GENERAL LEDGER</h1>
        <div className="mt-1 text-xs">{data.hotel_name || "Hotel Mutiara Merdeka"}</div>
        <div className="mt-1">Period: {period}{searchParams.get("search") ? ` · Search: ${searchParams.get("search")}` : ""}</div>
        {context.length > 0 && <div className="mt-0.5">Filters: {context.join(" · ")}</div>}
      </header>

      <table className="w-full border-collapse">
        <thead><tr>{[
          "Date", "Journal", "Account", "Description", "Document",
          "Context", "Debit", "Credit", "Balance",
        ].map((label) => <th key={label} className="border border-slate-700 px-2 py-1.5 text-left font-semibold">{label}</th>)}</tr></thead>
        <tbody>{rows.map((row: any, index: number) => {
          const contextPrimary = row.supplier_name || row.business_unit_name;
          const contextSecondary = [row.department_name, row.location_name].filter(Boolean).join(" · ");
          return <tr key={row.id}>
            <td className="border border-slate-500 px-2 py-1 whitespace-nowrap">{row.posting_date}</td>
            <td className="border border-slate-500 px-2 py-1 whitespace-nowrap">{row.journal_number}</td>
            <td className="border border-slate-500 px-2 py-1">{`${row.account_code} — ${row.account_name}`}</td>
            <td className="border border-slate-500 px-2 py-1">{row.description || "—"}</td>
            <td className="border border-slate-500 px-2 py-1 whitespace-nowrap">{row.reference_number || "—"}</td>
            <td className="border border-slate-500 px-2 py-1">{contextPrimary || contextSecondary || "—"}</td>
            <td className="border border-slate-500 px-2 py-1 text-right tabular-nums">{money(row.debit)}</td>
            <td className="border border-slate-500 px-2 py-1 text-right tabular-nums">{money(row.credit)}</td>
            <td className="border border-slate-500 px-2 py-1 text-right font-semibold tabular-nums">{money(row.balance)}</td>
          </tr>;
        })}</tbody>
        <tfoot><tr className="font-bold">
          <td colSpan={6} className="border border-slate-700 px-2 py-2 text-right">TOTAL</td>
          <td className="border border-slate-700 px-2 py-2 text-right">{money(data.total_debit)}</td>
          <td className="border border-slate-700 px-2 py-2 text-right">{money(data.total_credit)}</td>
          <td className="border border-slate-700 px-2 py-2" />
        </tr></tfoot>
      </table>

      <footer className="mt-4 flex justify-between text-[9px] text-slate-600">
        <span>Printed by {data.printed_by || "Finance"}</span>
        <span>{data.generated_at ? new Date(data.generated_at).toLocaleString() : ""}</span>
      </footer>
    </article>
  );
}