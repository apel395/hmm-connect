export type PrintColumn = { label: string; numeric?: boolean; code?: boolean };
export type PrintCell = string | number | null | undefined;
export type PrintGroup = {
  title: string;
  detail?: string;
  rows: PrintCell[][];
  footer?: PrintCell[];
};
export type InventoryPrintReport = {
  title: string;
  context: string;
  columns: PrintColumn[];
  groups: PrintGroup[];
  footer?: PrintCell[];
  summary?: string;
  rowCount: number;
};
export type ReportPage<T> = {
  items: T[];
  total_items: number;
  total_pages: number;
};

/** Print every authorized filtered row, refusing truncated or changing pagination. */
export async function collectReportPages<T extends { id: number }>(
  fetchPage: (page: number) => Promise<ReportPage<T>>,
) {
  const first = await fetchPage(1);
  if (
    !Array.isArray(first.items) ||
    !Number.isInteger(first.total_items) ||
    !Number.isInteger(first.total_pages) ||
    first.total_items < 0 ||
    first.total_pages < 0
  )
    throw new Error("Invalid report response");
  const items = [...first.items];
  for (let page = 2; page <= first.total_pages; page++) {
    const next = await fetchPage(page);
    if (!Array.isArray(next.items)) throw new Error("Invalid report response");
    if (
      next.total_items !== first.total_items ||
      next.total_pages !== first.total_pages
    )
      throw new Error("Data changed while preparing the report. Please retry.");
    items.push(...next.items);
  }
  if (
    items.length !== first.total_items ||
    new Set(items.map((row) => row.id)).size !== items.length
  )
    throw new Error("The complete report could not be loaded. Please retry.");
  return { ...first, items };
}

export const printNumber = (value: unknown) =>
  Number(value ?? 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });
export const printMoney = (value: unknown) =>
  "Rp " +
  Number(value ?? 0).toLocaleString("id-ID", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
const escape = (value: PrintCell) =>
  String(value ?? "—").replace(
    /[&<>"']/g,
    (ch) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        ch
      ]!,
  );

export function renderInventoryPrint(
  report: InventoryPrintReport,
  generatedBy: string,
  generatedAt = new Date(),
) {
  const cells = (row: PrintCell[], tag = "td") =>
    report.columns
      .map(
        (col, i) =>
          `<${tag} class="${col.numeric ? "numeric" : ""} ${col.code ? "code" : ""}">${escape(row[i])}</${tag}>`,
      )
      .join("");
  const timestamp = generatedAt.toLocaleString("id-ID", {
    timeZone: "Asia/Jakarta",
  });
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><title>${escape(report.title)}</title><style>
    @page { size: A4 landscape; margin: 12mm 10mm 15mm; @bottom-left { content: "MMH-Connect"; font: 8pt Arial; color: #555; } @bottom-right { content: "Page " counter(page) " / " counter(pages); font: 8pt Arial; color: #555; } }
    * { box-sizing: border-box; } body { margin: 0; color: #17211b; font: 9pt Arial, Helvetica, sans-serif; }
    .company { font-size: 9pt; font-weight: bold; } h1 { margin: 3mm 0 2mm; font-size: 15pt; } .meta { font-size: 8pt; line-height: 1.5; } .summary { margin-top: 3mm; font-weight: bold; }
    table { width: 100%; border-collapse: collapse; margin-top: 4mm; font-size: 8.5pt; } thead { display: table-header-group; } th { background: #edf1ee; border-top: 1px solid #7b887e; border-bottom: 1px solid #7b887e; text-align: left; } th, td { padding: 1.6mm 1.2mm; vertical-align: top; } td { border-bottom: 1px solid #e1e5e2; } .numeric { text-align: right; white-space: nowrap; font-variant-numeric: tabular-nums; } .code { font-weight: bold; white-space: nowrap; } tr { break-inside: avoid; } .group td { padding-top: 3mm; background: #f4f6f4; font-weight: bold; } .group { break-after: avoid; } .detail { font-weight: normal; font-size: 8pt; } .subtotal td { border-top: 1px solid #a8b2aa; font-weight: bold; } .grand td { border-top: 2px solid #56645a; font-weight: bold; } .empty { padding: 8mm; text-align: center; } th, .group td { print-color-adjust: exact; -webkit-print-color-adjust: exact; }
    @media screen { body { padding: 16px; background: white; } }
  </style></head><body><div class="company">MMH-Connect</div><h1>${escape(report.title)}</h1><div class="meta">${escape(report.context)}<br>Generated: ${escape(timestamp)} WIB · By: ${escape(generatedBy)} · Records: ${report.rowCount}</div>${report.summary ? `<div class="summary">${escape(report.summary)}</div>` : ""}<table><thead><tr>${report.columns.map((c) => `<th class="${c.numeric ? "numeric" : ""}">${escape(c.label)}</th>`).join("")}</tr></thead><tbody>${report.groups.map((group) => `<tr class="group"><td colspan="${report.columns.length}">${escape(group.title)}${group.detail ? `<div class="detail">${escape(group.detail)}</div>` : ""}</td></tr>${group.rows.map((row) => `<tr>${cells(row)}</tr>`).join("")}${group.footer ? `<tr class="subtotal">${cells(group.footer)}</tr>` : ""}`).join("")}${!report.groups.length ? `<tr><td class="empty" colspan="${report.columns.length}">No records match the selected filters.</td></tr>` : ""}${report.footer ? `<tr class="grand">${cells(report.footer)}</tr>` : ""}</tbody></table></body></html>`;
}
