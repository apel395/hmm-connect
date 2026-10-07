import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import Loading from "@/components/ui/Loading";
import { getLedgerPrint } from "./api";

const money = (value: unknown) => Number(value || 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

const longDate = (value?: string | null) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return `${String(parsed.getDate()).padStart(2, "0")} ${MONTHS[parsed.getMonth()]} ${parsed.getFullYear()}`;
};
const shortDate = (value?: string | null) => {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return `${String(parsed.getDate()).padStart(2, "0")}-${MONTHS_SHORT[parsed.getMonth()]}-${String(parsed.getFullYear()).slice(2)}`;
};

const COLUMNS = ["Date", "Journal No.", "Document", "Reference", "Description", "Location", "Dept", "Debit", "Credit", "Balance"];

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
  const filters = data.filters ?? {};
  const accounts: any[] = data.accounts ?? [];
  const control = data.control ?? {};
  const brand = data.brand_name || "MMH-Connect";
  const period = data.period?.date_from || data.period?.date_to
    ? `${longDate(data.period?.date_from) || "…"} - ${longDate(data.period?.date_to) || "…"}`
    : "All time";
  const accountLine = filters.account_code
    ? filters.account_name || "Selected account"
    : "ALL";

  return (
    <article className="gl-print mx-auto bg-white p-6 text-[10px] leading-tight text-slate-950 print:p-0">
      <style>{`
        @page { size: landscape; margin: 10mm 10mm 12mm 10mm; }
        @media print {
          body { background: #fff; }
          .gl-print { padding-top: 18mm; }
          .gl-running-header { position: fixed; top: 0; left: 10mm; right: 10mm; display: block !important; }
          .gl-print thead { display: table-header-group; }
          .gl-print tr { break-inside: avoid; page-break-inside: avoid; }
          .gl-account { break-inside: auto; }
        }
      `}</style>

      <header className="gl-running-header mb-3 border-b-2 border-slate-800 pb-2">
        <div className="grid grid-cols-[90px_1fr_90px] items-center">
          <img src="/logoprint.jpeg" alt="PT. Mutiara Merdeka Hotel" className="h-12 w-auto object-contain" />
          <div className="text-center"><h1 className="text-lg font-bold tracking-wide">{brand.toUpperCase()}</h1><h2 className="text-base font-semibold">GENERAL LEDGER</h2></div>
          <div />
        </div>
        <div className="text-[10px]">{period}</div>
        <div className="text-[9px] text-slate-700">Account: {accountLine}</div>
      </header>

      <section className="mb-4 grid grid-cols-3 gap-x-8 gap-y-0.5 text-[10px]">
        <div>Business Unit : {filters.business_unit_name || "All"}</div>
        <div>Location : {filters.location_name || "All"}</div>
        <div>Department : {filters.department_name || "All"}</div>
        <div>Reference Type : {filters.reference_type || "All"}</div>
        <div>Search : {filters.search || "—"}</div>
        <div>Printed : {data.generated_at ? new Date(data.generated_at).toLocaleString("en-GB") : ""}</div>
      </section>

      {accounts.map((account) => (
        <section key={account.account_id} className="gl-account mb-6">
          <div className="mb-1 border-b border-slate-500 pb-1">
            <div className="font-bold">{account.account_name}</div>
            <div>{account.account_name}</div>
            <div className="text-[9px] text-slate-600">{account.account_type} | Normal Balance: {account.normal_balance}</div>
          </div>

          <div className="mb-1 flex justify-between font-semibold">
            <span>Opening Balance</span>
            <span className="tabular-nums">{money(account.opening_balance)}</span>
          </div>

          <table className="w-full border-collapse">
            <thead>
              <tr>{COLUMNS.map((label, index) => (
                <th key={label} className={`border border-slate-700 px-1.5 py-1 font-semibold ${index >= 7 ? "text-right" : "text-left"} ${label === "Description" ? "w-[26%]" : "whitespace-nowrap"}`}>{label}</th>
              ))}</tr>
            </thead>
            <tbody>
              {account.rows.map((row: any) => (
                <tr key={row.id}>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{shortDate(row.posting_date)}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{row.journal_number}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{row.document_number || row.document_type || "—"}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{row.reference || "—"}</td>
                  <td className="border border-slate-400 px-1.5 py-0.5 break-words">{row.description || "—"}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{row.location_name || "—"}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{row.department_name || "—"}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5 text-right tabular-nums">{money(row.debit)}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5 text-right tabular-nums">{money(row.credit)}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5 text-right font-semibold tabular-nums">{money(row.balance)}</td>
                </tr>
              ))}
              {!account.rows.length && (
                <tr><td colSpan={10} className="border border-slate-400 px-1.5 py-1 text-center text-slate-500">No movements in this period</td></tr>
              )}
            </tbody>
            <tfoot>
              <tr className="font-bold">
                <td colSpan={7} className="border border-slate-700 px-1.5 py-1 text-right">ACCOUNT TOTAL</td>
                <td className="border border-slate-700 px-1.5 py-1 text-right tabular-nums">{money(account.total_debit)}</td>
                <td className="border border-slate-700 px-1.5 py-1 text-right tabular-nums">{money(account.total_credit)}</td>
                <td className="border border-slate-700 px-1.5 py-1" />
              </tr>
            </tfoot>
          </table>

          <div className="mt-1 flex justify-between font-semibold">
            <span>Closing Balance</span>
            <span className="tabular-nums">{money(account.closing_balance)}</span>
          </div>
        </section>
      ))}

      {!accounts.length && <p className="py-6 text-center text-slate-500">No ledger activity for the selected filters.</p>}

      <section className="mt-4 border-t-2 border-slate-800 pt-2">
        <div className="mb-1 text-center font-bold">GENERAL LEDGER CONTROL TOTAL</div>
        <div className="mx-auto flex w-72 justify-between"><span>Total Debits :</span><span className="tabular-nums">{money(control.total_debit)}</span></div>
        <div className="mx-auto flex w-72 justify-between"><span>Total Credits :</span><span className="tabular-nums">{money(control.total_credit)}</span></div>
        <div className="mx-auto flex w-72 justify-between font-bold"><span>Difference :</span><span className="tabular-nums">{money(control.difference)}</span></div>
      </section>

      <footer className="mt-4 flex justify-between text-[9px] text-slate-600">
        <span>Generated by {brand} · {data.hotel_name || ""}</span>
        <span>Printed by {data.printed_by || "Finance"}</span>
      </footer>
    </article>
  );
}
