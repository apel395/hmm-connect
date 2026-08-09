import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";

const tabs = [
  { label: "Overview", to: "/accounts-payable", exact: true },
  { label: "Aging", to: "/accounts-payable/aging" },
  { label: "Supplier Invoices", to: "/accounts-payable/invoices" },
  { label: "Payments", to: "/accounts-payable/payments" },
  { label: "Credit / Debit Notes", to: "/accounts-payable/adjustments" },
];

export default function APWorkspaceHeader() {
  return (
    <ModuleWorkspaceHeader
      title="Accounts Payable"
      description="Manage supplier liabilities, aging, invoices, payments, and adjustments from one workspace."
      tabs={tabs}
    />
  );
}
