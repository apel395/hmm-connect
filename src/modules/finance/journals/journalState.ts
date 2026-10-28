import type { Journal } from "./api";

type State = Pick<Journal, "status" | "period_locked" | "accounting_recognized" | "allowed_actions">;

export function journalAccountingLabel(journal: State): string {
  if (journal.period_locked) return "Locked";
  return journal.accounting_recognized ? "Recognized" : "Not recognized";
}

export function journalAllowsBulk(journal: State, action: "post" | "unpost"): boolean {
  if (journal.period_locked) return false;
  return journal.status === (action === "post" ? "DRAFT" : "POSTED") &&
    Boolean(journal.allowed_actions?.[action === "post" ? "can_post" : "can_unpost"]);
}
