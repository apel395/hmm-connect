/** Shared accounting amount formatting: Indonesian locale, exactly two decimals. */
export const MONEY_LOCALE = "id-ID";

export function moneyNumber(value: unknown): number {
  const parsed = Number(value ?? 0);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function formatMoney(value: unknown): string {
  return moneyNumber(value).toLocaleString(MONEY_LOCALE, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}
