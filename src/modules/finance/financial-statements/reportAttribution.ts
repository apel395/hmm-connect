import type { RelatedAccount, PresentationRow } from "./ProfitLossTable";

export function selectRelatedAccounts(accounts: RelatedAccount[], selected: PresentationRow | null) {
  return accounts.filter(account => selected?.member_keys ? selected.member_keys.includes(account.presentation_key ?? String(account.account_id)) : selected?.account_ids.includes(account.account_id));
}

// Income reduces total expenses and increases NOP.
export function contribution(account: RelatedAccount, selected: PresentationRow | null) {
  if (selected?.kind !== "subtotal") return 1;
  if (selected.key === "TOTAL_DEDUCTIONS") return account.category === "NONOPERATING_INCOME" ? -1 : 1;
  return account.category === "REVENUE" || account.category === "NONOPERATING_INCOME" ? 1 : -1;
}
