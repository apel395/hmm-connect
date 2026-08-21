import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";

const tabs = [
  { label: "Receivables Summary", to: "/accounts-receivable", exact: true },
  { label: "Receivables Detail", to: "/accounts-receivable/detail" },
  { label: "AR Aging", to: "/accounts-receivable/aging" },
];

export default function ARWorkspaceHeader() {
  return (
    <ModuleWorkspaceHeader
      title="Accounts Receivable"
      description="Review customer balances, receipts, invoice detail, and aging from one read-only workspace."
      tabs={tabs}
    />
  );
}
