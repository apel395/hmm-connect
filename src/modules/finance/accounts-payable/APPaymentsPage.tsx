import APWorkspaceHeader from "./APWorkspaceHeader";
import PaymentListPage from "@/modules/finance/payments/PaymentListPage";

export default function APPaymentsPage() {
  return <div className="space-y-5"><APWorkspaceHeader /><PaymentListPage /></div>;
}
