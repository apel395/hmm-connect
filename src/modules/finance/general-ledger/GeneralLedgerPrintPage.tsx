import { ledgerPrintParams } from "./printFilters";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import Empty from "@/components/ui/Empty";
import Loading from "@/components/ui/Loading";
import { apiErrorMessage } from "@/utils/apiError";
import { formatMoney, moneyNumber } from "@/utils/formatMoney";
import { safeSheetName } from "@/utils/exportPrintTables";
import { getLedgerPrint } from "./api";

const money = formatMoney;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const MONTHS_SHORT = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const COLUMNS = ["Posting Date", "Journal No.", "Source Document", "Reference", "Description", "Location", "Dept", "Debit", "Credit", "Running Balance"];
const LINE_COLUMNS = ["Account Code", "Account Name", "Posting Date", "Journal No.", "Source / Type", "Source Document", "Reference", "Description", "Location", "Department", "Debit", "Credit", "Running Balance"];
const DATA_SHEET = safeSheetName("GL Lines");
const SUMMARY_SHEET = safeSheetName("Account Summary");
const CONTROL_SHEET = safeSheetName("Control");
const AUDIT_SHEET = safeSheetName("Audit");

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
const numericCell = (value: unknown) => ({
  "data-v": moneyNumber(value),
  "data-t": "n",
  "data-z": "#,##0.00",
});

export default function GeneralLedgerPrintPage() {
  const [searchParams] = useSearchParams();
  const params = ledgerPrintParams(searchParams);
  const query = useQuery({
    queryKey: ["general-ledger", "print", params],
    queryFn: () => getLedgerPrint(params),
  });

  if (query.isLoading) return <Loading message="Loading general ledger…" />;
  if (query.isError) return <div role="alert" className="p-6 text-sm text-red-700">{apiErrorMessage(query.error, "General ledger could not be loaded.")}</div>;
  if (!query.data) return <div role="alert" className="p-6 text-sm text-red-700">General ledger could not be loaded.</div>;

  const data = query.data as any;
  const filters = data.filters ?? {};
  const accounts: any[] = data.accounts ?? [];
  const control = data.control ?? {};
  const brand = data.brand_name || "MMH-Connect";
  const period = data.period?.date_from || data.period?.date_to
    ? `${longDate(data.period?.date_from) || "…"} - ${longDate(data.period?.date_to) || "…"}`
    : "All time";
  const accountLine = filters.account_code
    ? `${filters.account_code} — ${filters.account_name || "Selected account"}`
    : "ALL";
  const printedAt = data.generated_at ? new Date(data.generated_at).toLocaleString("en-GB") : "";
  const generatedAt = data.generated_at ? new Date(data.generated_at).toISOString() : new Date().toISOString();
  const filteredScope = Object.entries(params).some(([, value]) => value && value !== "ALL");
  const movementLabel = filteredScope ? "MOVEMENT TOTAL (FILTERED)" : "MOVEMENT TOTAL";
  const closingLabel = filteredScope ? "Closing Balance (selected filters)" : "Closing Balance (carried forward)";
  const lastSummaryRow = accounts.length + 1;

  let lineRowCursor = 0;
  const lineRanges = accounts.map((account) => {
    const rowCount = Array.isArray(account.rows) ? account.rows.length : 0;
    const range = {
      start: lineRowCursor + 2,
      end: lineRowCursor + rowCount + 1,
      hasRows: rowCount > 0,
    };
    lineRowCursor += rowCount;
    return range;
  });

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
        <div>Search Type : {filters.search_type || "All"}</div>
        <div>Search : {filters.search || "—"}</div>
        <div>Supplier : {filters.supplier_name || "All"}</div>
        <div>Account Range : {filters.account_from_code || filters.account_to_code ? `${filters.account_from_code || "…"} - ${filters.account_to_code || "…"}` : "All"}</div>
        <div>Printed : {printedAt || "—"}</div>
      </section>

      {accounts.map((account) => {
        return <section key={account.account_id} className="gl-account mb-6">
          <div className="mb-1 border-b border-slate-500 pb-1">
            <div className="font-bold">{account.account_code} — {account.account_name}</div>
            <div className="text-[9px] text-slate-600">{account.account_type} | Normal Balance: {account.normal_balance}</div>
          </div>

          <div className="mb-1 flex justify-between font-semibold">
            <span>Opening Balance (brought forward)</span>
            <span className="tabular-nums">{money(account.opening_balance)}</span>
          </div>

          <table data-export-omit className="w-full border-collapse">
            <thead>
              <tr>{COLUMNS.map((label, index) => (
                <th key={label} className={`border border-slate-700 px-1.5 py-1 font-semibold ${index >= 7 ? "text-right" : "text-left"} ${label === "Description" ? "w-[26%]" : "whitespace-nowrap"}`}>{label}</th>
              ))}</tr>
            </thead>
            <tbody>
              {(account.rows ?? []).map((row: any) => (
                <tr key={row.id}>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{shortDate(row.posting_date)}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{row.journal_number}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{row.document_number || row.document_type || "—"}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{row.reference || "—"}</td>
                  <td className="border border-slate-400 px-1.5 py-0.5 break-words">{row.description || "—"}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{row.location_name || "—"}</td>
                  <td className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5">{row.department_name || "—"}</td>
                  <td {...numericCell(row.debit)} className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5 text-right tabular-nums">{money(row.debit)}</td>
                  <td {...numericCell(row.credit)} className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5 text-right tabular-nums">{money(row.credit)}</td>
                  <td {...numericCell(row.balance)} className="whitespace-nowrap border border-slate-400 px-1.5 py-0.5 text-right font-semibold tabular-nums">{money(row.balance)}</td>
                </tr>
              ))}
              {!account.rows?.length && (
                <tr><td colSpan={10} className="border border-slate-400 px-1.5 py-1 text-center text-slate-500">No movements in this period</td></tr>
              )}
            </tbody>
            <tfoot>
              <tr className="font-bold">
                <td colSpan={7} className="border border-slate-700 px-1.5 py-1 text-right">{movementLabel}</td>
                <td {...numericCell(account.total_debit)} className="border border-slate-700 px-1.5 py-1 text-right tabular-nums">{money(account.total_debit)}</td>
                <td {...numericCell(account.total_credit)} className="border border-slate-700 px-1.5 py-1 text-right tabular-nums">{money(account.total_credit)}</td>
                <td className="border border-slate-700 px-1.5 py-1" />
              </tr>
            </tfoot>
          </table>

          <div className="mt-1 flex justify-between font-semibold">
            <span>{closingLabel}</span>
            <span className="tabular-nums">{money(account.closing_balance)}</span>
          </div>
        </section>;
      })}

      {!accounts.length && <Empty title="No ledger activity" description="No ledger activity for the selected filters." />}

      <section className="mt-4 border-t-2 border-slate-800 pt-2">
        <div className="mb-1 text-center font-bold">FILTERED GENERAL LEDGER CONTROL TOTAL</div>
        <div className="mx-auto flex w-72 justify-between"><span>Total Debits :</span><span className="tabular-nums">{money(control.total_debit)}</span></div>
        <div className="mx-auto flex w-72 justify-between"><span>Total Credits :</span><span className="tabular-nums">{money(control.total_credit)}</span></div>
        <div className="mx-auto flex w-72 justify-between font-bold"><span>Difference :</span><span className="tabular-nums">{money(control.difference)}</span></div>
      </section>

      <div data-export-include className="hidden">
        <table data-export-sheet={DATA_SHEET}>
          <thead><tr>{LINE_COLUMNS.map((label) => <th key={label}>{label}</th>)}</tr></thead>
          <tbody>
            {accounts.flatMap((account) => (account.rows ?? []).map((row: any, rowIndex: number) => (
              <tr key={`${account.account_id}-${row.id ?? rowIndex}`}>
                <td>{account.account_code}</td>
                <td>{account.account_name}</td>
                <td>{row.posting_date || "—"}</td>
                <td>{row.journal_number || "—"}</td>
                <td>{row.document_type || row.reference_type || "—"}</td>
                <td>{row.document_number || row.document_type || "—"}</td>
                <td>{row.reference || "—"}</td>
                <td>{row.description || "—"}</td>
                <td>{row.location_name || "—"}</td>
                <td>{row.department_name || "—"}</td>
                <td {...numericCell(row.debit)}>{money(row.debit)}</td>
                <td {...numericCell(row.credit)}>{money(row.credit)}</td>
                <td {...numericCell(row.balance)}>{money(row.balance)}</td>
              </tr>
            )))}
          </tbody>
        </table>

        <table data-export-sheet={SUMMARY_SHEET} data-export-source-sheet={DATA_SHEET} data-export-autofilter="false">
          <thead><tr><th>Account Code</th><th>Account Name</th><th>Account Type</th><th>Normal Balance</th><th>Opening Balance</th><th>Debit Movement</th><th>Credit Movement</th><th>Closing Balance</th></tr></thead>
          <tbody>
            {accounts.map((account, index) => {
              const summaryRow = index + 2;
              const range = lineRanges[index];
              const debitNormal = String(account.normal_balance || "").toUpperCase() === "DEBIT";
              const closingFormula = range.hasRows
                ? debitNormal
                  ? `E${summaryRow}+F${summaryRow}-G${summaryRow}`
                  : `E${summaryRow}-F${summaryRow}+G${summaryRow}`
                : undefined;
              return <tr key={`summary-${account.account_id ?? index}`}>
                <td>{account.account_code}</td>
                <td>{account.account_name}</td>
                <td>{account.account_type || "—"}</td>
                <td>{account.normal_balance || "—"}</td>
                <td {...numericCell(account.opening_balance)}>{money(account.opening_balance)}</td>
                <td {...numericCell(account.total_debit)} data-f={range.hasRows ? `SUM(K${range.start}:K${range.end})` : undefined}>{money(account.total_debit)}</td>
                <td {...numericCell(account.total_credit)} data-f={range.hasRows ? `SUM(L${range.start}:L${range.end})` : undefined}>{money(account.total_credit)}</td>
                <td {...numericCell(account.closing_balance)} data-f={closingFormula} data-export-source-sheet="">{money(account.closing_balance)}</td>
              </tr>;
            })}
          </tbody>
        </table>

        <table data-export-sheet={CONTROL_SHEET} data-export-source-sheet={SUMMARY_SHEET} data-export-autofilter="false">
          <thead><tr><th>Field</th><th>Value</th></tr></thead>
          <tbody>
            <tr><td>REPORT</td><td>GENERAL LEDGER</td></tr>
            <tr><td>PERIOD</td><td>{period}</td></tr>
            <tr><td>ACCOUNT</td><td>{accountLine}</td></tr>
            <tr><td>BUSINESS UNIT</td><td>{filters.business_unit_name || "All"}</td></tr>
            <tr><td>LOCATION</td><td>{filters.location_name || "All"}</td></tr>
            <tr><td>DEPARTMENT</td><td>{filters.department_name || "All"}</td></tr>
            <tr><td>REFERENCE TYPE</td><td>{filters.reference_type || "All"}</td></tr>
            <tr><td>SEARCH TYPE</td><td>{filters.search_type || "All"}</td></tr>
            <tr><td>SEARCH</td><td>{filters.search || "—"}</td></tr>
            <tr><td>TOTAL DEBITS</td><td {...numericCell(control.total_debit)} data-f={accounts.length ? `SUM(F2:F${lastSummaryRow})` : undefined}>{money(control.total_debit)}</td></tr>
            <tr><td>TOTAL CREDITS</td><td {...numericCell(control.total_credit)} data-f={accounts.length ? `SUM(G2:G${lastSummaryRow})` : undefined}>{money(control.total_credit)}</td></tr>
            <tr><td>DIFFERENCE</td><td {...numericCell(control.difference)} data-f={accounts.length ? `SUM(F2:F${lastSummaryRow})-SUM(G2:G${lastSummaryRow})` : undefined}>{money(control.difference)}</td></tr>
            <tr><td>GENERATED AT</td><td>{generatedAt}</td></tr>
          </tbody>
        </table>

        <table data-export-sheet={AUDIT_SHEET} data-export-autofilter="false">
          <thead><tr><th>Field</th><th>Value</th></tr></thead>
          <tbody>
            <tr><td>SOURCE</td><td>Print preview</td></tr>
            <tr><td>ENTITY</td><td>{brand}</td></tr>
            <tr><td>HOTEL</td><td>{data.hotel_name || "—"}</td></tr>
            <tr><td>PRINTED BY</td><td>{data.printed_by || "Finance"}</td></tr>
            <tr><td>GENERATED AT</td><td>{generatedAt}</td></tr>
          </tbody>
        </table>
      </div>

      <footer className="mt-4 flex justify-between text-[9px] text-slate-600">
        <span>Generated by {brand} · {data.hotel_name || ""}</span>
        <span>Printed by {data.printed_by || "Finance"}</span>
      </footer>
    </article>
  );
}
