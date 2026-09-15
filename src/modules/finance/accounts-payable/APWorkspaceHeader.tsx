import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";

const tabs = [
  { label: "Payables Summary", to: "/accounts-payable", exact: true },
  { label: "Payables Detail", to: "/accounts-payable/detail" },
  { label: "AP Aging", to: "/accounts-payable/aging" },
  { label: "Supplier Invoices", to: "/accounts-payable/invoices" },
  { label: "Payments", to: "/accounts-payable/payments" },
  { label: "Payment Vouchers", to: "/finance/payment-vouchers" },
  { label: "Credit / Debit Notes", to: "/accounts-payable/adjustments" },
];

export default function APWorkspaceHeader() {
  return (
    <ModuleWorkspaceHeader
      title="Accounts Payable"
      description="Review supplier liabilities, payments, vouchers, aging, invoices, and adjustments from one workspace."
      tabs={tabs}
    />
  );
}
