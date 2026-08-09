import ModuleWorkspaceHeader from "@/components/workspace/ModuleWorkspaceHeader";
import JournalListPage from "./JournalListPage";
import GeneralLedgerPage from "@/modules/finance/general-ledger/GeneralLedgerPage";
import TrialBalancePage from "@/modules/finance/trial-balance/TrialBalancePage";

type Section = "journal" | "general-ledger" | "trial-balance";

const tabs = [
  { label: "Journal", to: "/journal", exact: true },
  { label: "General Ledger", to: "/journal/general-ledger" },
  { label: "Trial Balance", to: "/journal/trial-balance" },
];

export default function JournalWorkspacePage({ section }: { section: Section }) {
  return (
    <div className="space-y-5">
      <ModuleWorkspaceHeader
        title="Journal"
        description="Review manual journals, general ledger activity, and trial balance from one workspace."
        tabs={tabs}
      />
      {section === "journal" && <JournalListPage />}
      {section === "general-ledger" && <GeneralLedgerPage />}
      {section === "trial-balance" && <TrialBalancePage />}
    </div>
  );
}
