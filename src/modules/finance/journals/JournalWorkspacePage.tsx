import { NavLink } from "react-router-dom";
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
    <div className="workspace-accounting-shell">
      <nav className="workspace-accounting-nav print:hidden" aria-label="Accounting modules">{tabs.map(tab => <NavLink key={tab.to} to={tab.to} end={tab.exact} className={({ isActive }) => isActive ? "is-active" : ""}>{tab.label}</NavLink>)}</nav>
      {section === "journal" && <JournalListPage />}
      {section === "general-ledger" && <GeneralLedgerPage />}
      {section === "trial-balance" && <TrialBalancePage />}
    </div>
  );
}
