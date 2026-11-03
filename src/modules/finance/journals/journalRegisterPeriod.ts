/** The month shortcut mirrors the existing inclusive date-range API filters. */
export function journalMonthRange(month: string): { from: string; to: string } | null {
  if (!/^\d{4}-(0[1-9]|1[0-2])$/.test(month)) return null;
  const [year, monthNumber] = month.split("-").map(Number);
  const lastDay = new Date(Date.UTC(year, monthNumber, 0)).getUTCDate();
  return { from: `${month}-01`, to: `${month}-${String(lastDay).padStart(2, "0")}` };
}

export function journalSelectedMonth(from: string, to: string): string {
  const month = /^\d{4}-(0[1-9]|1[0-2])-01$/.test(from) ? from.slice(0, 7) : "";
  const range = month ? journalMonthRange(month) : null;
  return range?.to === to ? month : "";
}
