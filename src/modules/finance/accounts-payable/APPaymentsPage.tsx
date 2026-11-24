import DataWorkspace from "@/components/workspace/DataWorkspace";
import PaymentListPage from "@/modules/finance/payments/PaymentListPage";
import APWorkspaceHeader from "./APWorkspaceHeader";

export default function APPaymentsPage() {
  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="space-y-2">
        <APWorkspaceHeader />
        <PaymentListPage />
      </div>
    </DataWorkspace>
  );
}
