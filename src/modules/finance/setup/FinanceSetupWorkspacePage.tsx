import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";
import ChartOfAccountPage from "@/modules/master/chart-of-accounts/pages/ChartOfAccountPage";
import PostingRulesPage from "@/modules/finance/posting-rules/PostingRulesPage";
import BankAccountsSetupPage from "./BankAccountsSetupPage";

type Section = "coa" | "posting-rules" | "bank-accounts";

const tabs = [
  { label: "Chart of Accounts", to: "/finance-setup", exact: true },
  { label: "Direct COA", to: "/finance-setup/posting-rules" },
  { label: "Bank Accounts", to: "/finance-setup/bank-accounts" },
];

export default function FinanceSetupWorkspacePage({ section }: { section: Section }) {
  return (
    <div className="space-y-5">
      <ModuleWorkspaceHeader
        title="Finance Setup"
        description="Configure chart of accounts, direct master mappings, and bank accounts."
        tabs={tabs}
      />
      {section === "coa" && <ChartOfAccountPage />}
      {section === "posting-rules" && <PostingRulesPage />}
      {section === "bank-accounts" && <BankAccountsSetupPage />}
    </div>
  );
}
