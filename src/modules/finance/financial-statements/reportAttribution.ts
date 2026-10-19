import type { RelatedAccount, PresentationRow } from "./ProfitLossTable";

export function selectRelatedAccounts(accounts: RelatedAccount[], selected: PresentationRow | null) {
  return accounts.filter(account => selected?.member_keys ? selected.member_keys.includes(account.presentation_key ?? String(account.account_id)) : selected?.account_ids.includes(account.account_id));
}
