export type AgingDateRange = { date_from?: string; date_to?: string };

/** Inclusive `YYYY-MM-DD` comparison used by AP aging screen and print filters. */
export function inAgingDateRange(date: string | null | undefined, range: AgingDateRange) {
  if (!date) return true;
  if (range.date_from && date < range.date_from) return false;
  if (range.date_to && date > range.date_to) return false;
  return true;
}

export function agingDateRangeFromSearch(search: URLSearchParams): AgingDateRange {
  const date_from = search.get("date_from") || undefined;
  const date_to = search.get("date_to") || undefined;
  if (date_from && date_to && date_from > date_to) return {};
  return { date_from, date_to };
}

export function agingDateRangeParams(range: AgingDateRange) {
  const search = new URLSearchParams();
  if (range.date_from) search.set("date_from", range.date_from);
  if (range.date_to) search.set("date_to", range.date_to);
  return search;
}
