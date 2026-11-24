import DataWorkspace from "@/components/workspace/DataWorkspace";
import SupplierInvoiceListPage from "@/modules/finance/supplier-invoices/SupplierInvoiceListPage";
import APWorkspaceHeader from "./APWorkspaceHeader";

export default function APInvoicesPage() {
  return (
    <DataWorkspace area="Accounting" className="data-first">
      <div className="space-y-2">
        <APWorkspaceHeader />
        <SupplierInvoiceListPage />
      </div>
    </DataWorkspace>
  );
}
