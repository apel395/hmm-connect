import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import Loading from "@/components/ui/Loading";
import FinancialReportPrintTemplate from "@/components/print/FinancialReportPrintTemplate";
import { listJournals, getJournalScope } from "./api";

const money = (value: unknown) =>
  Number(value || 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

async function loadAll(params: Record<string, unknown>) {
  const rows: any[] = [];
  let page = 1;

  while (true) {
    const data = await listJournals({ ...params, page, page_size: 100 });
    rows.push(...(data.items ?? []));
    if (!data.has_next) break;
    page += 1;
  }

  return rows;
}

export default function JournalRegisterPrintPage() {
  const [searchParams] = useSearchParams();
  const params = Object.fromEntries(
    Object.entries({
      search: searchParams.get("search") || "",
      status: searchParams.get("status") || "",
      location_id: searchParams.get("location_id") || "",
      business_unit_id: searchParams.get("business_unit_id") || "",
      supplier_id: searchParams.get("supplier_id") || "",
      date_from: searchParams.get("date_from") || "",
      date_to: searchParams.get("date_to") || "",
      account_id: searchParams.get("account_id") || "",
      department_id: searchParams.get("department_id") || "",
      reference_type: searchParams.get("reference_type") || "",
      balance_state: searchParams.get("balance_state") || "ALL",
      difference_amount: searchParams.get("difference_amount") || "",
    }).filter(([, value]) => value !== ""),
  );

  const query = useQuery({
    queryKey: ["journal-register-print", params],
    queryFn: () => loadAll(params),
  });

  const scope = useQuery({ queryKey: ["journal-scope"], queryFn: getJournalScope });
  if (query.isLoading || scope.isLoading) return <Loading />;
  if (!query.data) return <p>Journal register could not be loaded.</p>;

  const rows = query.data;
  const totalDebit = rows.reduce((sum: number, row: any) => sum + Number(row.total_debit || 0), 0);
  const totalCredit = rows.reduce((sum: number, row: any) => sum + Number(row.total_credit || 0), 0);

  return (
    <FinancialReportPrintTemplate
      title="Journal Register"
      subtitle="Complete journal listing for the selected filters"
      filters={[
        { label: "Search", value: params.search || "All" },
        { label: "Status", value: params.status || "All" },
        { label: "Location", value: scope.data?.locations.find(row => row.id === Number(params.location_id || (scope.data?.location_locked ? scope.data.default_location_id : 0)))?.name || "All locations" },
        { label: "Unit", value: scope.data?.units.find(row => row.id === Number(params.business_unit_id))?.name || "All units" },
        { label: "Journal Count", value: rows.length },
      ]}
      columns={[
        { label: "Journal No.", render: (row: any) => row.journal_number },
        { label: "Date", render: (row: any) => row.journal_date },
        { label: "Document", render: (row: any) => row.reference_number || "—" },
        { label: "Type", render: (row: any) => String(row.reference_type || "").replaceAll("_", " ") || "—" },
        { label: "Description", render: (row: any) => row.description || "—" },
        { label: "Location", render: (row: any) => row.location_name || "—" },
        { label: "Debit", align: "right", render: (row: any) => money(row.total_debit) },
        { label: "Credit", align: "right", render: (row: any) => money(row.total_credit) },
        { label: "Status", render: (row: any) => row.status },
      ]}
      rows={rows}
      rowKey={(row: any) => row.id}
      footerRows={
        <tr className="font-bold">
          <td colSpan={6} className="border border-slate-700 px-1.5 py-1 text-right">CONTROL TOTAL</td>
          <td className="border border-slate-700 px-1.5 py-1 text-right tabular-nums">{money(totalDebit)}</td>
          <td className="border border-slate-700 px-1.5 py-1 text-right tabular-nums">{money(totalCredit)}</td>
          <td className="border border-slate-700 px-1.5 py-1" />
        </tr>
      }
      control={
        <div className="mx-auto grid w-80 grid-cols-2 gap-y-1">
          <span>Total Debits</span><span className="text-right tabular-nums">{money(totalDebit)}</span>
          <span>Total Credits</span><span className="text-right tabular-nums">{money(totalCredit)}</span>
          <span className="font-bold">Difference</span><span className="text-right font-bold tabular-nums">{money(totalDebit - totalCredit)}</span>
        </div>
      }
    />
  );
}

