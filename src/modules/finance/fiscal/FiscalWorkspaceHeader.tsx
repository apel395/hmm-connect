import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";

const tabs = [
  { label: "COA & Mapping", to: "/finance/fiscal/coa", exact: true },
  { label: "Reconciliation", to: "/finance/fiscal/reconciliation" },
  { label: "Balance Sheet", to: "/finance/fiscal/balance-sheet" },
  { label: "Lampiran 1D", to: "/finance/fiscal/lampiran-1d" },
  { label: "SPT Tahunan 1771", to: "/finance/fiscal/spt-1771" },
  { label: "Fiscal Periods", to: "/finance/fiscal/periods" },
];

export default function FiscalWorkspaceHeader() {
  return (
    <ModuleWorkspaceHeader
      title="Fiscal"
      description="Coretax L1-D Jasa workspace — commercial-to-fiscal COA mapping, reconciliation (ekualisasi), balance sheet, the Lampiran 1D attachment, and annual corporate tax return (SPT 1771)."
      tabs={tabs}
    />
  );
}