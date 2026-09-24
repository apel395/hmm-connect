import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import api from "@/api/client";
import Loading from "@/components/ui/Loading";
import FinancialReportPrintTemplate from "@/components/print/FinancialReportPrintTemplate";
import { listBankAccounts } from "@/modules/finance/cash-flow/bankAccountApi";
import { openingBalanceApi } from "@/modules/finance/opening-balances/api";
import { getAccounts, getAllAccountLookup } from "@/modules/master/chart-of-accounts/api";
import type { AccountParams } from "@/modules/master/chart-of-accounts/api";

type Section = "coa" | "posting-rules" | "bank-accounts" | "opening-balances" | "accounting-periods";

const money = (value: unknown) =>
  Number(value || 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

const directCoaLabels: Record<string, string> = {
  accounts_payable_account_id: "Global Accounts Payable",
  grni_account_id: "Goods Received Not Invoiced (GRNI)",
  input_vat_account_id: "Input VAT",
  purchase_discount_account_id: "Purchase Discount",
  withholding_tax_payable_account_id: "Withholding Tax Payable",
};

async function loadAllAccounts(params: Omit<AccountParams, "page" | "page_size">) {
  const rows: any[] = [];
  let page = 1;
  while (true) {
    const data = await getAccounts({ ...params, page, page_size: 100 });
    rows.push(...(data.items ?? []));
    if (!data.total_pages || page >= data.total_pages) break;
    page += 1;
  }
  return rows;
}

export default function FinanceSetupPrintPage({ section }: { section: Section }) {
  const [searchParams] = useSearchParams();
  const year = Number(searchParams.get("year") || new Date().getFullYear());

  const coaParams = {
    search: searchParams.get("search") || undefined,
    account_type: (searchParams.get("account_type") || undefined) as any,
    normal_balance: (searchParams.get("normal_balance") || undefined) as any,
    is_posting: searchParams.get("is_posting") === "true" ? true : searchParams.get("is_posting") === "false" ? false : undefined,
    is_active: searchParams.get("is_active") === "true" ? true : searchParams.get("is_active") === "false" ? false : undefined,
    sort_by: searchParams.get("sort_by") || "account_code",
    sort_order: searchParams.get("sort_order") === "desc" ? "desc" as const : "asc" as const,
  };

  const coa = useQuery({
    queryKey: ["finance-setup-print", "coa", coaParams],
    queryFn: async () => {
      const [rows, lookup] = await Promise.all([
        loadAllAccounts(coaParams),
        getAllAccountLookup({}),
      ]);
      return { rows, lookup };
    },
    enabled: section === "coa",
  });

  const direct = useQuery({
    queryKey: ["finance-setup-print", "posting-rules"],
    queryFn: async () => {
      const [settings, accounts] = await Promise.all([
        api.get("/accounting/direct-coa-settings").then((r) => r.data as any),
        getAllAccountLookup({ is_active: true, is_posting: true }),
      ]);
      return { settings, accounts };
    },
    enabled: section === "posting-rules",
  });

  const banks = useQuery({
    queryKey: ["finance-setup-print", "bank-accounts"],
    queryFn: () => listBankAccounts(false),
    enabled: section === "bank-accounts",
  });

  const opening = useQuery({
    queryKey: ["finance-setup-print", "opening-balances", year],
    queryFn: async () => (await openingBalanceApi.list(year)).data,
    enabled: section === "opening-balances",
  });

  const periods = useQuery({
    queryKey: ["finance-setup-print", "accounting-periods", year],
    queryFn: async () => (await api.get("/fiscal-periods", { params: { fiscal_year: year } })).data as any[],
    enabled: section === "accounting-periods",
  });

  const loading = [coa, direct, banks, opening, periods].some((q) => q.isLoading && q.fetchStatus !== "idle");
  if (loading) return <Loading />;

  if (section === "coa") {
    const rows = coa.data?.rows ?? [];
    const parentName = new Map((coa.data?.lookup ?? []).map((row: any) => [row.id, row.account_name]));
    return (
      <FinancialReportPrintTemplate
        title="Chart of Accounts Register"
        subtitle="Complete chart of accounts for the selected filters"
        filters={[
          { label: "Search", value: coaParams.search || "All" },
          { label: "Account Type", value: coaParams.account_type || "All" },
          { label: "Normal Balance", value: coaParams.normal_balance || "All" },
          { label: "Account Count", value: rows.length },
        ]}
        columns={[
          { label: "Code", render: (row: any) => row.account_code },
          { label: "Account Name", render: (row: any) => row.account_name },
          { label: "Type", render: (row: any) => row.account_type },
          { label: "Subtype", render: (row: any) => row.account_subtype || "—" },
          { label: "Parent", render: (row: any) => row.parent_account_id ? parentName.get(row.parent_account_id) || "—" : "—" },
          { label: "Normal", render: (row: any) => row.normal_balance },
          { label: "Posting", render: (row: any) => row.is_posting ? "Yes" : "No" },
          { label: "Cash Flow", render: (row: any) => row.cash_flow_category || "—" },
          { label: "FS Group", render: (row: any) => row.financial_statement_group || "—" },
          { label: "Status", render: (row: any) => row.is_active ? "Active" : "Archived" },
        ]}
        rows={rows}
        rowKey={(row: any) => row.id}
      />
    );
  }

  if (section === "posting-rules") {
    const settings = direct.data?.settings ?? {};
    const accounts = direct.data?.accounts ?? [];
    const byId = new Map(accounts.map((row: any) => [row.id, row]));
    const rows = Object.entries(directCoaLabels).map(([field, label]) => {
      const account = byId.get(settings[field]);
      return {
        field,
        label,
        account_code: account?.account_code || "—",
        account_name: account?.account_name || "Not configured",
        status: settings[field] ? "Configured" : "Missing",
      };
    });
    return (
      <FinancialReportPrintTemplate
        title="Direct COA Configuration"
        subtitle="Global accounting control account mappings"
        orientation="portrait"
        filters={[
          { label: "Setup Status", value: settings.is_complete ? "Complete" : "Incomplete" },
          { label: "Mappings", value: rows.length },
        ]}
        columns={[
          { label: "Control", render: (row: any) => row.label },
          { label: "COA Code", render: (row: any) => row.account_code },
          { label: "Account Name", render: (row: any) => row.account_name },
          { label: "Status", render: (row: any) => row.status },
        ]}
        rows={rows}
        rowKey={(row: any) => row.field}
      />
    );
  }

  if (section === "bank-accounts") {
    const rows = banks.data ?? [];
    return (
      <FinancialReportPrintTemplate
        title="Bank Account Register"
        subtitle="Configured bank and cash funding accounts"
        filters={[{ label: "Account Count", value: rows.length }]}
        columns={[
          { label: "Bank", render: (row: any) => row.bank_name },
          { label: "Account Name", render: (row: any) => row.account_name },
          { label: "Account Number", render: (row: any) => row.account_number },
          { label: "Business Unit", render: (row: any) => row.business_unit_name || "—" },
          { label: "Location", render: (row: any) => row.location_name || "Global / all locations" },
          { label: "Linked COA", render: (row: any) => [row.coa_account_code, row.coa_account_name].filter(Boolean).join(" — ") || "—" },
          { label: "Payment", render: (row: any) => row.is_payment_account ? "Yes" : "No" },
          { label: "Status", render: (row: any) => row.is_active ? "Active" : "Inactive" },
        ]}
        rows={rows}
        rowKey={(row: any) => row.id}
      />
    );
  }

  if (section === "opening-balances") {
    const rows = opening.data?.items ?? [];
    const debit = rows.filter((row: any) => row.balance_type === "DEBIT").reduce((sum: number, row: any) => sum + Number(row.amount || 0), 0);
    const credit = rows.filter((row: any) => row.balance_type === "CREDIT").reduce((sum: number, row: any) => sum + Number(row.amount || 0), 0);
    return (
      <FinancialReportPrintTemplate
        title="Opening Balance Report"
        subtitle={"Fiscal Year " + year + " · posted entries only"}
        filters={[
          { label: "Fiscal Year", value: year },
          { label: "Posted Entries", value: rows.length },
        ]}
        columns={[
          { label: "Code", render: (row: any) => row.account_code },
          { label: "Account Name", render: (row: any) => row.account_name },
          { label: "Type", render: (row: any) => row.account_type || "—" },
          { label: "Debit", align: "right", render: (row: any) => row.balance_type === "DEBIT" ? money(row.amount) : "—" },
          { label: "Credit", align: "right", render: (row: any) => row.balance_type === "CREDIT" ? money(row.amount) : "—" },
          { label: "Posted At", render: (row: any) => row.posted_at ? new Date(row.posted_at).toLocaleString("id-ID") : "—" },
        ]}
        rows={rows}
        rowKey={(row: any) => row.id}
        footerRows={
          <tr className="font-bold">
            <td colSpan={3} className="border border-slate-700 px-1.5 py-1 text-right">TOTAL</td>
            <td className="border border-slate-700 px-1.5 py-1 text-right">{money(debit)}</td>
            <td className="border border-slate-700 px-1.5 py-1 text-right">{money(credit)}</td>
            <td className="border border-slate-700 px-1.5 py-1" />
          </tr>
        }
        control={
          <div className="mx-auto grid w-80 grid-cols-2 gap-y-1">
            <span>Total Debit</span><span className="text-right">{money(debit)}</span>
            <span>Total Credit</span><span className="text-right">{money(credit)}</span>
            <span className="font-bold">Difference</span><span className="text-right font-bold">{money(debit - credit)}</span>
          </div>
        }
      />
    );
  }

  const rows = periods.data ?? [];
  return (
    <FinancialReportPrintTemplate
      title="Accounting Period Register"
      subtitle={"Fiscal Year " + year}
      orientation="portrait"
      filters={[
        { label: "Fiscal Year", value: year },
        { label: "Configured Periods", value: rows.length + " / 12" },
        { label: "Open Periods", value: rows.filter((row: any) => row.is_open && !row.is_closed).length },
      ]}
      columns={[
        { label: "Period", render: (row: any) => row.period_name },
        { label: "Start Date", render: (row: any) => row.start_date },
        { label: "End Date", render: (row: any) => row.end_date },
        { label: "Status", render: (row: any) => row.is_open && !row.is_closed ? "OPEN" : "CLOSED" },
      ]}
      rows={rows}
      rowKey={(row: any) => row.id}
    />
  );
}
