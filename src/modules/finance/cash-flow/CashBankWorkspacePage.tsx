import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";
import CashFlowDashboardPage from "./CashFlowDashboardPage";
import CashAccountsPage from "./CashAccountsPage";
import BankTransferListPage from "./BankTransferListPage";
import BankReconciliationListPage from "@/modules/finance/bank-reconciliation/BankReconciliationListPage";
import CashFlowStatementPage from "./CashFlowStatementPage";

type Section = "overview" | "accounts" | "transfers" | "reconciliation" | "cash-flow";

const tabs = [
  { label: "Overview", to: "/cash-bank", exact: true },
  { label: "Bank Accounts", to: "/cash-bank/accounts" },
  { label: "Transfers", to: "/cash-bank/transfers" },
  { label: "Reconciliation", to: "/cash-bank/reconciliation" },
  { label: "Cash Flow", to: "/cash-bank/cash-flow" },
];

export default function CashBankWorkspacePage({ section }: { section: Section }) {
  return (
    <div className="space-y-5">
      <ModuleWorkspaceHeader
        title="Cash & Bank"
        description="Manage bank accounts, transfers, reconciliation, and cash flow from one workspace."
        tabs={tabs}
      />
      {section === "overview" && <CashFlowDashboardPage />}
      {section === "accounts" && <CashAccountsPage />}
      {section === "transfers" && <BankTransferListPage />}
      {section === "reconciliation" && <BankReconciliationListPage />}
      {section === "cash-flow" && <CashFlowStatementPage />}
    </div>
  );
}
