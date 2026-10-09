import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { listLocations, listBusinessUnits, listDepartments } from "@/modules/admin/organization/api";
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

  const locations = useQuery({ queryKey: ["trial-print-locations"], queryFn: () => listLocations({ is_active: true }), enabled: !!params.location_id });
  const units = useQuery({ queryKey: ["trial-print-units"], queryFn: listBusinessUnits, enabled: !!params.business_unit_id });
  const departments = useQuery({ queryKey: ["trial-print-departments"], queryFn: () => listDepartments({ business_unit_id: params.business_unit_id }), enabled: !!params.department_id });
  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>Trial balance could not be loaded.</p>;

  const rows = query.data.rows;

  return (
    <FinancialReportPrintTemplate
      title="Trial Balance"
      subtitle={`Opening ${Number(params.date_from.slice(0, 4))-1}-12-31 · Movement ${params.date_from} to ${params.date_to} · Rupiah (IDR)`}
      filters={[
        { label: "Search", value: params.search || "All accounts" },
        { label: "Location", value: params.location_id ? locations.data?.find(row => row.id === params.location_id)?.name || "Selected location" : "Consolidated" },
        ...(params.business_unit_id ? [{ label: "Unit", value: units.data?.find(row => row.id === params.business_unit_id)?.name || "Selected unit" }] : []),
        ...(params.department_id ? [{ label: "Department", value: departments.data?.find(row => row.id === params.department_id)?.name || "Selected department" }] : []),
        { label: "Include Zero Balance", value: params.include_zero_balance ? "Yes" : "No" },
        { label: "Account Count", value: rows.length },
      ]}
      columns={[
        { label: "Account", render: (row) => row.account_name },
        { label: "Opening Balance", align: "right", render: (row) => money(row.opening_balance) },
        ...(params.date_from.slice(5) !== "01-01" ? [
          { label: "Prior Debit", align: "right" as const, render: (row: TrialBalanceRow) => money(row.prior_debit) },
          { label: "Prior Credit", align: "right" as const, render: (row: TrialBalanceRow) => money(row.prior_credit) },
        ] : []),
        { label: "Debit Movement", align: "right", render: (row) => money(row.period_debit) },
        { label: "Credit Movement", align: "right", render: (row) => money(row.period_credit) },
        { label: "Closing", align: "right", render: (row) => money(row.closing_balance) },
        { label: "Status", render: (row) => row.status === "ABNORMAL" ? "Abnormal" : "Normal" },
      ]}
      rows={rows}
      rowKey={(row) => row.account_id}

    />
  );
}
