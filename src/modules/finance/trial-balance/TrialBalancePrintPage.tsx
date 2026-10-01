import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import Loading from "@/components/ui/Loading";
import FinancialReportPrintTemplate from "@/components/print/FinancialReportPrintTemplate";
import { getTrialBalance, type TrialBalanceFilters, type TrialBalanceRow } from "./api";

const money = (value: unknown) =>
  Number(value || 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

async function loadAll(params: TrialBalanceFilters) {
  const rows: TrialBalanceRow[] = [];
  let page = 1;

  while (true) {
    const data = await getTrialBalance({ ...params, page, page_size: 100 });
    rows.push(...data.items);
    if (!data.has_next) break;
    page += 1;
  }

  return { rows };
}

export default function TrialBalancePrintPage() {
  const [searchParams] = useSearchParams();
  const params: TrialBalanceFilters = {
    date_from: searchParams.get("date_from") || new Date().toISOString().slice(0, 10),
    date_to: searchParams.get("date_to") || new Date().toISOString().slice(0, 10),
    search: searchParams.get("search") || undefined,
    account_type: searchParams.get("account_type") || undefined,
    account_id: searchParams.get("account_id") ? Number(searchParams.get("account_id")) : undefined,
    parent_account_id: searchParams.get("parent_account_id") ? Number(searchParams.get("parent_account_id")) : undefined,
    include_zero_balance: searchParams.get("include_zero_balance") === "true",
    include_inactive: searchParams.get("include_inactive") === "true",
    location_id: searchParams.get("location_id") ? Number(searchParams.get("location_id")) : undefined,
    department_id: searchParams.get("department_id") ? Number(searchParams.get("department_id")) : undefined,
    business_unit_id: searchParams.get("business_unit_id") ? Number(searchParams.get("business_unit_id")) : undefined,
    sort_by: searchParams.get("sort_by") || undefined,
    sort_order: searchParams.get("sort_order") === "desc" ? "desc" : "asc",
  };

  const query = useQuery({
    queryKey: ["trial-balance-print", params],
    queryFn: () => loadAll(params),
  });

  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>Trial balance could not be loaded.</p>;

  const rows = query.data.rows;
  const totalDebit = rows.reduce((sum, row) => sum + Number(row.period_debit || 0), 0);
  const totalCredit = rows.reduce((sum, row) => sum + Number(row.period_credit || 0), 0);

  return (
    <FinancialReportPrintTemplate
      title="Trial Balance"
      subtitle={`Opening ${params.date_from.slice(0, 4)}-01-01 · Movement through ${params.date_to}`}
      filters={[
        { label: "Search", value: params.search || "All accounts" },
        { label: "Location ID", value: params.location_id || "All" },
        { label: "Include Zero Balance", value: params.include_zero_balance ? "Yes" : "No" },
        { label: "Account Count", value: rows.length },
      ]}
      columns={[
        { label: "COA No.", render: (row) => row.account_code },
        { label: "COA Name", render: (row) => row.account_name },
        { label: "Opening Balance", align: "right", render: (row) => money(row.opening_balance) },
        { label: "Debit Movement", align: "right", render: (row) => money(row.period_debit) },
        { label: "Credit Movement", align: "right", render: (row) => money(row.period_credit) },
        { label: "Closing", align: "right", render: (row) => money(row.closing_balance) },
        { label: "Status", render: (row) => row.status === "ABNORMAL" ? "Abnormal" : "Normal" },
      ]}
      rows={rows}
      rowKey={(row) => row.account_id}
      footerRows={
        <tr className="font-bold">
          <td colSpan={3} className="border border-slate-700 px-1.5 py-1 text-right">TOTAL MOVEMENT</td>
          <td className="border border-slate-700 px-1.5 py-1 text-right tabular-nums">{money(totalDebit)}</td>
          <td className="border border-slate-700 px-1.5 py-1 text-right tabular-nums">{money(totalCredit)}</td>
          <td className="border border-slate-700 px-1.5 py-1" />
          <td className="border border-slate-700 px-1.5 py-1" />
        </tr>
      }
    />
  );
}
