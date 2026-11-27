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

/**
 * Keep printed amounts as readable text while exporting real numbers and
 * formulas. Print markup can opt in with data-v (raw value), data-f (formula),
 * data-z (number format), and data-excel-address (explicit cell address).
 */
function applyCellMetadata(sheet: any, table: HTMLTableElement) {
  Array.from(table.rows).forEach((row, rowIndex) => {
    let columnIndex = 0;
    Array.from(row.cells).forEach((element) => {
      const cell = element as HTMLTableCellElement;
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
      if (formula) target.f = formula.trim().replace(/^=/, "");

      columnIndex += Math.max(1, cell.colSpan || 1);
    });
  });
}

/** Export the tables already rendered in a print preview to a workbook. */
export function exportTablesToExcel(root: ParentNode | null | undefined, fileName: string) {
  const tables = Array.from(root?.querySelectorAll("table") ?? []) as HTMLTableElement[];
  if (!tables.length) throw new Error("No printable table is available to export");
  const workbook = XLSX.utils.book_new();
  tables.forEach((table, index) => {
    const sheet = XLSX.utils.table_to_sheet(table);
    applyCellMetadata(sheet, table);
    XLSX.utils.book_append_sheet(workbook, sheet, `Sheet ${index + 1}`.slice(0, 31));
  });
  XLSX.writeFile(workbook, `${fileName}.xlsx`);
}

/** Safe workbook name derived from a print title. */
export function printExcelFileName(title: string) {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "report";
}
