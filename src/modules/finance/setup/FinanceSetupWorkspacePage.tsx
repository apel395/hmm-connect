import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";
import ChartOfAccountPage from "@/modules/master/chart-of-accounts/pages/ChartOfAccountPage";
import PostingRulesPage from "@/modules/finance/posting-rules/PostingRulesPage";
import BankAccountsSetupPage from "./BankAccountsSetupPage";
import OpeningBalancesPage from "@/modules/finance/opening-balances/OpeningBalancesPage";

type Section = "coa" | "posting-rules" | "bank-accounts" | "opening-balances";

const tabs = [
  { label: "Chart of Accounts", to: "/finance-setup", exact: true },
  { label: "Direct COA", to: "/finance-setup/posting-rules" },
  { label: "Bank Accounts", to: "/finance-setup/bank-accounts" },
  { label: "Opening Balances", to: "/finance-setup/opening-balances" },
];

export default function FinanceSetupWorkspacePage({ section }: { section: Section }) {
  return (
    <div className="space-y-5">
      <ModuleWorkspaceHeader
        title="Finance Setup"
        description="Configure chart of accounts, direct master mappings, bank accounts, and opening balances."
        tabs={tabs}
      />
      {section === "coa" && <ChartOfAccountPage />}
      {section === "posting-rules" && <PostingRulesPage />}
      {section === "bank-accounts" && <BankAccountsSetupPage />}
      {section === "opening-balances" && <OpeningBalancesPage />}
    </div>
  );
}
