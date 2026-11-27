import * as XLSX from "xlsx";

/** Export the tables already rendered in a print preview to a workbook. */
export function exportTablesToExcel(root: ParentNode | null | undefined, fileName: string) {
  const tables = Array.from(root?.querySelectorAll("table") ?? []);
  if (!tables.length) throw new Error("No printable table is available to export");
  const workbook = XLSX.utils.book_new();
  tables.forEach((table, index) => {
    const sheet = XLSX.utils.table_to_sheet(table as HTMLElement);
    XLSX.utils.book_append_sheet(workbook, sheet, `Sheet ${index + 1}`.slice(0, 31));
  });
  XLSX.writeFile(workbook, `${fileName}.xlsx`);
}

/** Safe workbook name derived from a print title. */
export function printExcelFileName(title: string) {
  return title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "report";
}
