import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";

const tabs = [
  { label: "COA & Mapping", to: "/fiscal/coa", exact: true },
  { label: "Reconciliation", to: "/fiscal/reconciliation" },
  { label: "Balance Sheet", to: "/fiscal/balance-sheet" },
  { label: "Lampiran 1D", to: "/fiscal/lampiran-1d" },
  { label: "SPT Tahunan 1771", to: "/fiscal/spt-1771" },
  { label: "Fiscal Periods", to: "/fiscal/periods" },
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