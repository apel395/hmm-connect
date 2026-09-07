import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";

const tabs = [
  { label: "COA & Mapping", to: "/fiscal/coa", exact: true },
  { label: "Ekualisasi", to: "/fiscal/reconciliation" },
  { label: "Neraca", to: "/fiscal/balance-sheet" },
  { label: "Lampiran 1D", to: "/fiscal/lampiran-1d" },
  { label: "SPT 1771", to: "/fiscal/spt-1771" },
  { label: "Periode Fiskal", to: "/fiscal/periods" },
];

export default function FiscalWorkspaceHeader() {
  return (
    <ModuleWorkspaceHeader
      title="Fiscal"
      description="Coretax L1-D Jasa workspace — commercial to fiscal mapping, reconciliation (ekualisasi), balance sheet, the Lampiran 1D attachment, and SPT Tahunan 1771."
      tabs={tabs}
    />
  );
}