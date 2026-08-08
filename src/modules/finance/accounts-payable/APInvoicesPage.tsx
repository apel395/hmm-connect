import APWorkspaceHeader from "./APWorkspaceHeader";
import SupplierInvoiceListPage from "@/modules/finance/supplier-invoices/SupplierInvoiceListPage";

export default function APInvoicesPage() {
  return <div className="space-y-5"><APWorkspaceHeader /><SupplierInvoiceListPage /></div>;
}
