import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";
import ChartOfAccountPage from "@/modules/master/chart-of-accounts/pages/ChartOfAccountPage";
import PostingRulesPage from "@/modules/finance/posting-rules/PostingRulesPage";
import BankAccountsSetupPage from "./BankAccountsSetupPage";
import OpeningBalancesPage from "@/modules/finance/opening-balances/OpeningBalancesPage";
import FiscalPeriodsPage from "@/modules/finance/fiscal/pages/FiscalPeriodsPage";

type Section = "coa" | "posting-rules" | "bank-accounts" | "opening-balances" | "accounting-periods";

const tabs = [
  { label: "Chart of Accounts", to: "/finance-setup", exact: true },
  { label: "Direct COA", to: "/finance-setup/posting-rules" },
  { label: "Bank Accounts", to: "/finance-setup/bank-accounts" },
  { label: "Opening Balances", to: "/finance-setup/opening-balances" },
  { label: "Accounting Periods", to: "/finance-setup/accounting-periods" },
];

export default function FinanceSetupWorkspacePage({ section }: { section: Section }) {
  return (
    <div className="space-y-5">
      <ModuleWorkspaceHeader
        title="Finance Setup"
        description="Configure chart of accounts, direct master mappings, bank accounts, opening balances, and accounting periods."
        tabs={tabs}
      />
      {section === "coa" && <ChartOfAccountPage />}
      {section === "posting-rules" && <PostingRulesPage />}
      {section === "bank-accounts" && <BankAccountsSetupPage />}
      {section === "opening-balances" && <OpeningBalancesPage />}
      {section === "accounting-periods" && <FiscalPeriodsPage />}
    </div>
  );
}
