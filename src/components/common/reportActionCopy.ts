/**
 * Export and print actions must state what they act on. Most list exports are
 * built from the rows already loaded for the visible page, so the default is
 * deliberately explicit about that scope rather than a generic "Export".
 */
export type ExportScope = "page" | "filtered" | "dataset";

export const EXPORT_SCOPE_LABEL: Record<ExportScope, string> = {
  page: "current page",
  filtered: "all filtered rows",
  dataset: "all rows",
};

/** Canonical label for a report export, including file format. */
export function exportActionLabel(scope: ExportScope, format: "csv" | "excel"): string {
  return `Export ${EXPORT_SCOPE_LABEL[scope]} ${format === "csv" ? "CSV" : "to Excel"}`;
}

/** Used where a shared accounting document template stands in for a dedicated form. */
export const GENERIC_JOURNAL_PRINT_NOTE =
  "Print preview uses the shared accounting document template. For the formal register, open Journal → Journal Register.";

/** Used by register-style reports that share the financial report layout. */
export const GENERIC_REPORT_PRINT_NOTE =
  "Print preview uses the shared financial report layout. The printed report includes the filters shown above.";
