import { buildGeneralLedgerReport, exportGeneralLedgerWorkbook } from "@/utils/generalLedgerExcel";
import { getLedgerPrint, type LedgerPrintParams } from "./api";

/**
 * Download the same compact workbook used by the print preview Excel button.
 * Values still come from the backend print endpoint; only presentation is local.
 */
export async function downloadGeneralLedgerReport(params: LedgerPrintParams, fileName = "general-ledger") {
  const data = await getLedgerPrint(params);
  const report = buildGeneralLedgerReport(data, params as Record<string, string>);
  await exportGeneralLedgerWorkbook(report, fileName);
}
