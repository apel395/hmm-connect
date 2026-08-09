import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";
import ChartOfAccountPage from "@/modules/master/chart-of-accounts/pages/ChartOfAccountPage";
import PostingRulesPage from "@/modules/finance/posting-rules/PostingRulesPage";
import FiscalPeriodsPage from "@/modules/finance/fiscal-periods/FiscalPeriodsPage";

type Section = "coa" | "posting-rules" | "fiscal-periods";

const tabs = [
  { label: "Chart of Accounts", to: "/finance-setup", exact: true },
  { label: "Posting Rules", to: "/finance-setup/posting-rules" },
  { label: "Fiscal Periods", to: "/finance-setup/fiscal-periods" },
];

export default function FinanceSetupWorkspacePage({ section }: { section: Section }) {
  return (
    <div className="space-y-5">
      <ModuleWorkspaceHeader
        title="Finance Setup"
        description="Configure chart of accounts, automatic posting rules, and fiscal periods."
        tabs={tabs}
      />
      {section === "coa" && <ChartOfAccountPage />}
      {section === "posting-rules" && <PostingRulesPage />}
      {section === "fiscal-periods" && <FiscalPeriodsPage />}
    </div>
  );
}
