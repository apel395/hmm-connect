import DataWorkspace from "@/components/workspace/DataWorkspace";
import SupplierAdjustmentsPage from "@/modules/finance/supplier-adjustments/SupplierAdjustmentsPage";
import APWorkspaceHeader from "./APWorkspaceHeader";

export default function APAdjustmentsPage() {
  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="space-y-2">
        <APWorkspaceHeader />
        <SupplierAdjustmentsPage />
      </div>
    </DataWorkspace>
  );
}
