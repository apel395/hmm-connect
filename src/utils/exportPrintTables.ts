import * as XLSX from "xlsx";

const columnName = (index: number) => {
  let value = index + 1;
  let name = "";
  while (value > 0) {
    const remainder = (value - 1) % 26;
    name = String.fromCharCode(65 + remainder) + name;
    value = Math.floor((value - 1) / 26);
  }
  return name;
};

const cellReference = (row: number, column: number) => `${columnName(column)}${row + 1}`;

const parseCellReference = (reference: string): { row: number; column: number } | null => {
  const match = /^([A-Z]+)(\d+)$/.exec(reference.trim().toUpperCase());
  if (!match) return null;
  const column = match[1].split("").reduce((total, letter) => total * 26 + letter.charCodeAt(0) - 64, 0) - 1;
  return { row: Number(match[2]) - 1, column };
};

/** Excel sheet names cannot contain these characters and are capped at 31 chars. */
export function safeSheetName(value: string) {
  return (value.replace(/[\\/?*[\]:]/g, " ").trim() || "Sheet").slice(0, 31);
}

const quoteSheet = (value: string) => `'${value.replace(/'/g, "''")}'`;

/**
 * Summary-sheet formulas are authored against the data sheet in plain A1 form.
 * Qualify them here so a Control or Account Summary sheet can reference the
 * correct worksheet without forcing every print page to know the final name.
 */
function qualifyFormula(formula: string, source?: string | null) {
  const cleaned = formula.trim().replace(/^=/, "");
  if (!source || cleaned.includes("!")) return cleaned;
  return cleaned.replace(/\b([A-Z]{1,3}\d+(?::[A-Z]{1,3}\d+)?)\b/g, `${quoteSheet(source)}!$1`);
}

/**
 * Keep printed amounts as readable text while exporting real numbers and
 * formulas. Print markup can opt in with data-v (raw value), data-f (formula),
 * data-z (number format), data-excel-address (explicit cell address), and
 * data-export-source-sheet (formula source when the summary lives elsewhere).
 * Tables can also declare data-export-autofilter-range, data-export-freeze-row
 * and data-export-widths for purpose-built single-sheet exports.
 */
function applyCellMetadata(sheet: any, table: HTMLTableElement) {
  const tableSource = table.getAttribute("data-export-source-sheet") ?? undefined;
  Array.from(table.rows).forEach((row, rowIndex) => {
    let columnIndex = 0;
    Array.from(row.cells).forEach((element) => {
      const cell = element as HTMLTableCellElement;
      if (cell.closest("[data-export-omit]")) return;
      const override = parseCellReference(cell.getAttribute("data-excel-address") ?? "");
      const address = override ?? { row: rowIndex, column: columnIndex };
      const reference = cellReference(address.row, address.column);
      const target = sheet[reference] ?? (sheet[reference] = { t: "s", v: "" });

      const raw = cell.getAttribute("data-v");
      if (raw != null && raw !== "") {
        const numeric = Number(raw);
        if (Number.isFinite(numeric)) {
          target.t = "n";
          target.v = numeric;
        } else {
          target.t = "s";
          target.v = raw;
        }
      }
      const format = cell.getAttribute("data-z");
      if (format != null && format !== "") target.z = format;
      const formula = cell.getAttribute("data-f");
      if (formula) target.f = qualifyFormula(formula, cell.getAttribute("data-export-source-sheet") ?? tableSource);

      columnIndex += Math.max(1, cell.colSpan || 1);
    });
  });

  // Export tables can live in a visually hidden container; keep their rows
  // visible once the workbook is opened.
  const rowInfo = sheet["!rows"];
  if (Array.isArray(rowInfo)) rowInfo.forEach((info: any) => { if (info) info.hidden = false; });
}

function decorateSheet(sheet: any, table: HTMLTableElement) {
  const header = table.rows[0];
  const headers = Array.from(header?.cells ?? []) as HTMLTableCellElement[];
  const explicitWidths = (table.getAttribute("data-export-widths") ?? "")
    .split(",")
    .map((value) => Number(value.trim()))
    .filter((value) => Number.isFinite(value) && value > 0);
  const columnCount = Math.max(
    1,
    explicitWidths.length,
    headers.reduce((total, cell) => total + Math.max(1, cell.colSpan || 1), 0),
  );
  const rowCount = Math.max(1, table.rows.length);
  const filterRange = table.getAttribute("data-export-autofilter-range");
  if (filterRange) sheet["!autofilter"] = { ref: filterRange };
  else if (table.getAttribute("data-export-autofilter") !== "false") {
    sheet["!autofilter"] = { ref: `A1:${columnName(columnCount - 1)}${rowCount}` };
  }
  const freezeRow = Math.max(1, Number(table.getAttribute("data-export-freeze-row")) || 1);
  sheet["!views"] = [{ state: "frozen", ySplit: freezeRow, topLeftCell: `A${freezeRow + 1}`, activePane: "bottomLeft", pane: "bottomLeft" }];
  sheet["!cols"] = explicitWidths.length
    ? explicitWidths.map((wch) => ({ wch }))
    : headers.map((cell) => ({
        wch: Math.min(48, Math.max(12, (cell.textContent || "").trim().length + 4)),
      }));
}

/** Export the tables already rendered in a print preview to a workbook. */
export function exportTablesToExcel(root: ParentNode | null | undefined, fileName: string) {
  const tables = (Array.from(root?.querySelectorAll("table") ?? []) as HTMLTableElement[]).filter(
    (table) => !table.hasAttribute("data-export-omit") && !table.closest("[data-export-omit]"),
  );
  if (!tables.length) throw new Error("No printable table is available to export");

  const workbook = XLSX.utils.book_new();
  const usedNames = new Set<string>();
  const generatedAt = new Date().toISOString();
  Object.assign(workbook, {
    Props: {
      Title: fileName,
      Subject: "Print report export",
      Creator: "MMH-Connect",
      Description: "Generated from print preview",
      CreatedAt: new Date(),
    },
    Custprops: { ExportSource: "Print preview", GeneratedAt: generatedAt },
  });

  tables.forEach((table) => {
    const base = safeSheetName(table.getAttribute("data-export-sheet") || `Sheet ${usedNames.size + 1}`);
    let name = base;
    let suffixIndex = 2;
    while (usedNames.has(name)) {
      const suffix = ` (${suffixIndex++})`;
      name = `${base.slice(0, 31 - suffix.length)}${suffix}`;
    }
    usedNames.add(name);

    const sheet = XLSX.utils.table_to_sheet(table);
    applyCellMetadata(sheet, table);
    decorateSheet(sheet, table);
    XLSX.utils.book_append_sheet(workbook, sheet, name);
  });
  XLSX.writeFile(workbook, `${fileName}.xlsx`);
}

/** Safe workbook name derived from a print title. */
export function printExcelFileName(title: string) {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "report";
}
