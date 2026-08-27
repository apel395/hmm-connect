import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";
import CashFlowDashboardPage from "./CashFlowDashboardPage";
import BankTransferListPage from "./BankTransferListPage";
import BankReconciliationListPage from "@/modules/finance/bank-reconciliation/BankReconciliationListPage";
import CashFlowStatementPage from "./CashFlowStatementPage";

type Section = "overview" | "transfers" | "reconciliation" | "cash-flow";

const tabs = [
  { label: "Overview", to: "/cash-bank", exact: true },
  { label: "Transfers", to: "/cash-bank/transfers" },
  { label: "Reconciliation", to: "/cash-bank/reconciliation" },
  { label: "Cash Flow", to: "/cash-bank/cash-flow" },
];

export default function CashBankWorkspacePage({ section }: { section: Section }) {
  return (
    <div className="space-y-5">
      <ModuleWorkspaceHeader
        title="Cash & Bank"
        description="Review cash activity, transfers, reconciliation, and cash flow. Bank account configuration is managed in Administration → Finance Setup."
        tabs={tabs}
      />
      {section === "overview" && <CashFlowDashboardPage />}
      {section === "transfers" && <BankTransferListPage />}
      {section === "reconciliation" && <BankReconciliationListPage />}
      {section === "cash-flow" && <CashFlowStatementPage />}
    </div>
  );
}
