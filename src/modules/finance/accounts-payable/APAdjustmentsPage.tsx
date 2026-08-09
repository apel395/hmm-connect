import APWorkspaceHeader from "./APWorkspaceHeader";
import SupplierAdjustmentsPage from "@/modules/finance/supplier-adjustments/SupplierAdjustmentsPage";

export default function APAdjustmentsPage() {
  return (
    <div className="space-y-5">
      <APWorkspaceHeader />
      <SupplierAdjustmentsPage />
    </div>
  );
}
