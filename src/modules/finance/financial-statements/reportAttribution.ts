import type { RelatedAccount, PresentationRow } from "./ProfitLossTable";

export function selectRelatedAccounts(accounts: RelatedAccount[], selected: PresentationRow | null) {
  return accounts.filter(account => selected?.member_keys ? selected.member_keys.includes(account.presentation_key ?? String(account.account_id)) : selected?.account_ids.includes(account.account_id));
}

// The source-format subtotal exposes its signed account contributions.
export function contribution(account: RelatedAccount, selected: PresentationRow | null) {
  if (selected?.kind !== "subtotal") return 1;
  if (selected.key === "TOTAL_DEDUCTIONS") return account.category === "NONOPERATING_INCOME" && !account.nop_deduction ? -1 : 1;
  return account.category === "REVENUE" || (account.category === "NONOPERATING_INCOME" && !account.nop_deduction) ? 1 : -1;
}
