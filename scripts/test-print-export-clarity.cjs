/* global require, __dirname, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const req = require("node:module").createRequire(root + "/package.json");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
const has = (file, needle, message) =>
  assert.ok(read(file).includes(needle), `${message}: ${file} missing ${JSON.stringify(needle)}`);

async function run() {
  const copyBundle = await req("esbuild").build({
    absWorkingDir: root,
    tsconfig: root + "/tsconfig.app.json",
    entryPoints: ["src/components/common/reportActionCopy.ts"],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
  });
  const copyModule = { exports: {} };
  new Function("module", "exports", "require", copyBundle.outputFiles[0].text)(
    copyModule,
    copyModule.exports,
    (name) => req(name),
  );
  const { EXPORT_SCOPE_LABEL, exportActionLabel, GENERIC_JOURNAL_PRINT_NOTE, GENERIC_REPORT_PRINT_NOTE } =
    copyModule.exports;
  assert.deepEqual(EXPORT_SCOPE_LABEL, {
    page: "current page",
    filtered: "all filtered rows",
    dataset: "all rows",
  });
  assert.equal(exportActionLabel("page", "csv"), "Export current page CSV");
  assert.equal(exportActionLabel("filtered", "csv"), "Export all filtered rows CSV");
  assert.equal(exportActionLabel("dataset", "csv"), "Export all rows CSV");
  assert.equal(exportActionLabel("filtered", "excel"), "Export all filtered rows to Excel");
  assert.equal(exportActionLabel("dataset", "excel"), "Export all rows to Excel");
  assert.equal(
    GENERIC_JOURNAL_PRINT_NOTE,
    "Print preview uses the shared accounting document template. For the formal register, open Journal → Journal Register.",
  );
  assert.equal(
    GENERIC_REPORT_PRINT_NOTE,
    "Print preview uses the shared financial report layout. The printed report includes the filters shown above.",
  );

  has("src/components/common/ReportActions.tsx", "export function ExportButton", "shared export button exists");
  has("src/components/common/ReportActions.tsx", "export function ReportScopeNote", "scope note component exists");
  has("src/components/common/ReportActions.tsx", "title={text}", "export button exposes its scope in the title");
  has("src/components/common/ReportActions.tsx", "aria-label={text}", "export button exposes its scope accessibly");
  has("src/components/common/ReportActions.tsx", "print:hidden", "scope notes never print");

  const toolbar = read("src/components/common/ListToolbar.tsx");
  assert.ok(
    toolbar.includes("{onExport && (exportLabel ? <ExportButton label={exportLabel} onClick={onExport}/>"),
    "toolbar uses the explicit export label only when an export handler exists",
  );
  assert.ok(!toolbar.includes("onClick={onExport ?? (() => {})}", "toolbar has no no-op export button"));

  for (const file of [
    "src/modules/finance/accounts-payable/APReportingPage.tsx",
    "src/modules/finance/accounts-receivable/ARReportingPage.tsx",
    "src/modules/finance/accounts-payable/APMovementPage.tsx",
    "src/modules/purchasing/market-list/MarketListPage.tsx",
    "src/modules/purchasing/requisition/pages/PurchaseRequisitionListPage.tsx",
    "src/modules/purchasing/purchase-order/pages/PurchaseOrderListPage.tsx",
  ]) {
    has(file, 'exportLabel="Export current page CSV"', "current-page export is explicit");
  }

  for (const [file, scope, format] of [
    ["src/modules/finance/fiscal/pages/Lampiran1DPage.tsx", "filtered", "csv"],
    ["src/modules/finance/fiscal/pages/FiscalAccountPage.tsx", "page", "csv"],
    ["src/modules/finance/budgets/BudgetVsActualPage.tsx", "filtered", "csv"],
    ["src/modules/finance/budgets/BudgetVsActualPage.tsx", "filtered", "excel"],
    ["src/modules/finance/trial-balance/TrialBalancePage.tsx", "filtered", "excel"],
    ["src/modules/finance/general-ledger/GeneralLedgerPage.tsx", "filtered", "excel"],
    ["src/modules/finance/financial-statements/FinancialReportPage.tsx", "filtered", "excel"],
    ["src/modules/finance/opening-balances/OpeningBalancesPage.tsx", "filtered", "excel"],
    ["src/modules/finance/fixed-assets/FixedAssetReportPage.tsx", "filtered", "excel"],
    ["src/modules/finance/fixed-assets/DepreciationReportPage.tsx", "filtered", "excel"],
    ["src/modules/finance/fixed-assets/AssetFiscalReport.tsx", "filtered", "excel"],
    ["src/modules/finance/fixed-assets/AmortizationPage.tsx", "dataset", "excel"],
    ["src/modules/warehouse/inventory/pages/InventoryPeriodReportPage.tsx", "filtered", "excel"],
    ["src/modules/purchasing-documents/PurchasingDocumentsPage.tsx", "page", "csv"],
  ]) {
    assert.ok(
      new RegExp(`scope="${scope}"\\s+format="${format}"`).test(read(file)),
      `report export scope and format are explicit in ${file}`,
    );
  }

  const preview = read("src/components/print/PrintPreviewButton.tsx");
  assert.ok(preview.includes("note?: string"), "print preview accepts a UI-only note");
  assert.ok(
    preview.includes('{note && <ReportScopeNote className="mb-2">{note}</ReportScopeNote>}'),
    "print preview note renders inside the dialog, outside the iframe",
  );
  has("src/modules/finance/journals/JournalDetailPage.tsx", "note={GENERIC_JOURNAL_PRINT_NOTE}", "journal document note is shown");
  has("src/modules/finance/journals/JournalListPage.tsx", "note={GENERIC_REPORT_PRINT_NOTE}", "journal register note is shown");
  has("src/modules/finance/trial-balance/TrialBalancePage.tsx", "note={GENERIC_REPORT_PRINT_NOTE}", "trial balance note is shown");

  has("src/utils/formatMoney.ts", '"id-ID"', "shared accounting money format is Indonesian");
  for (const file of [
    "src/modules/finance/journals/JournalDetailPage.tsx",
    "src/modules/finance/journals/JournalListPage.tsx",
    "src/modules/finance/AccountingPrintPage.tsx",
    "src/modules/finance/general-ledger/GeneralLedgerPrintPage.tsx",
    "src/modules/finance/journals/JournalRegisterPrintPage.tsx",
  ]) {
    assert.ok(!read(file).includes("toLocaleString(undefined"), `journal and GL amounts use one format in ${file}`);
  }
  has("src/modules/finance/journals/JournalDetailPage.tsx", "<TH>Side</TH>", "journal detail names the debited or credited side");
  has("src/modules/finance/AccountingPrintPage.tsx", 'label: "LINE"', "journal voucher uses a standard line number column");
  has("src/modules/finance/AccountingPrintPage.tsx", 'label: "ACCOUNT CODE"', "journal print shows the account code");
  has("src/modules/finance/AccountingPrintPage.tsx", 'label: "ACCOUNT NAME"', "journal print names the account");
  assert.ok(!read("src/modules/finance/AccountingPrintPage.tsx").includes('label: "SIDE"'), "journal voucher relies on debit/credit columns instead of a redundant side column");
  has("src/modules/finance/AccountingPrintPage.tsx", "SUM(E2:E", "journal print-to-Excel debits use a SUM formula");
  has("src/modules/finance/AccountingPrintPage.tsx", "SUM(F2:F", "journal print-to-Excel credits use a SUM formula");
  has("src/modules/finance/AccountingPrintPage.tsx", "excelTable={journalExcelTable}", "journal voucher replaces multi-sheet export with one worksheet");
  has("src/modules/finance/AccountingPrintPage.tsx", 'data-export-sheet="Journal Voucher"', "journal voucher exports one named worksheet");
  has("src/modules/finance/journals/JournalRegisterPrintPage.tsx", 'label: "Debit Accounts"', "journal register names debited accounts");
  has("src/modules/finance/journals/JournalRegisterPrintPage.tsx", 'label: "Credit Accounts"', "journal register names credited accounts");
  has("src/modules/finance/journals/JournalRegisterPrintPage.tsx", 'label: "Source / Category"', "journal register names the source category");
  has("src/modules/finance/journals/JournalRegisterPrintPage.tsx", "SUM(I${registerDataStart}:I${registerDataEnd})", "journal register Excel debits are formula-driven");
  has("src/modules/finance/journals/JournalRegisterPrintPage.tsx", "excelTable={registerExcelTable}", "journal register replaces multi-sheet export with one worksheet");
  has("src/modules/finance/journals/JournalRegisterPrintPage.tsx", 'data-export-sheet="Journal Register"', "journal register exports one named worksheet");
  has("src/modules/finance/general-ledger/GeneralLedgerPrintPage.tsx", '"Running Balance"', "GL print uses a standard running balance column");
  has("src/modules/finance/general-ledger/GeneralLedgerPrintPage.tsx", '"Posting Date"', "GL print uses the posting date label");
  assert.ok(!read("src/modules/finance/general-ledger/GeneralLedgerPrintPage.tsx").includes('"Side"'), "GL print relies on debit/credit columns instead of a redundant side column");
  has("src/modules/finance/general-ledger/GeneralLedgerPrintPage.tsx", "Opening Balance (brought forward)", "GL print includes the opening balance");
  has("src/modules/finance/general-ledger/GeneralLedgerPrintPage.tsx", "MOVEMENT TOTAL (FILTERED)", "GL movement total names the filtered scope");
  const glPrint = read("src/modules/finance/general-ledger/GeneralLedgerPrintPage.tsx");
  assert.ok(glPrint.includes('data-export-generator="general-ledger"'), "GL print hands the compact workbook a typed model");
  assert.ok(glPrint.includes("buildGeneralLedgerReport("), "GL print builds its Excel presentation model from backend data");
  assert.ok(!glPrint.includes("EXPORT_HEADERS"), "GL Excel no longer uses the trial-balance-shaped export table");
  assert.ok(!glPrint.includes("Row Type"), "GL Excel has no technical Row Type column");
  assert.equal((glPrint.match(/data-export-sheet=/g) ?? []).length, 0, "GL Excel no longer relies on the generic table exporter");
  const glExcel = read("src/utils/generalLedgerExcel.ts");
  has("src/utils/generalLedgerExcel.ts", 'GL_SHEET = "General Ledger"', "GL exports a dedicated accounting worksheet");
  has("src/utils/generalLedgerExcel.ts", 'GL_INFO_SHEET = "Report Info"', "secondary GL metadata moves to Report Info");
  has("src/utils/generalLedgerExcel.ts", "OPENING BALANCE", "GL opening balance sits directly above transactions");
  has("src/utils/generalLedgerExcel.ts", "Net Movement", "GL reconciliation reports net movement instead of a balance-check difference");
  has("src/utils/generalLedgerExcel.ts", "Closing Balance", "GL reconciliation reports the closing balance");
  has("src/utils/generalLedgerExcel.ts", "_xlnm.Print_Titles", "GL worksheet repeats transaction headers when printed");
  has("src/utils/generalLedgerExcel.ts", 'orientation="landscape"', "GL worksheet prints in landscape");
  has("src/utils/generalLedgerExcel.ts", 'fitToWidth="1"', "GL worksheet fits all columns to one page wide");
  has("src/utils/generalLedgerExcel.ts", "showGridLines", "GL worksheet hides worksheet gridlines");
  assert.ok(!glExcel.includes('"Row Type"'), "GL workbook has no technical Row Type column");
  assert.ok(!glExcel.includes('"Difference"'), "GL workbook has no misleading single-account difference");
  for (const file of [
    "src/modules/finance/AccountingPrintPage.tsx",
    "src/modules/finance/journals/JournalRegisterPrintPage.tsx",
  ]) {
    const text = read(file);
    assert.equal((text.match(/data-export-sheet=/g) ?? []).length, 1, `${file} exports exactly one worksheet`);
    assert.ok(!text.includes('data-export-sheet="Control"'), `${file} has no separate control sheet`);
    assert.ok(!text.includes('data-export-sheet="Audit"'), `${file} has no separate audit sheet`);
  }
  has("src/components/print/DocumentPrintTemplate.tsx", "data-export-omit={excelTable ? \"\" : undefined}", "document print can defer to a purpose-built worksheet");
  has("src/components/print/FinancialReportPrintTemplate.tsx", "data-export-omit={excelTable ? \"\" : undefined}", "report print can defer to a purpose-built worksheet");
  has("src/components/print/DocumentPrintTemplate.tsx", 'data-export-sheet="Control"', "document default export still carries control data");
  has("src/components/print/DocumentPrintTemplate.tsx", 'data-export-sheet="Audit"', "document default export still carries audit data");
  has("src/components/print/DocumentPrintTemplate.tsx", 'data-f={total.formula}', "document totals carry Excel formulas");
  has("src/components/print/FinancialReportPrintTemplate.tsx", 'data-export-sheet="Control"', "report default export still carries control data");
  has("src/components/print/FinancialReportPrintTemplate.tsx", "data-v={hasRaw ? Number(raw) : undefined}", "report rows carry raw numeric values");
  has("src/utils/exportPrintTables.ts", "safeSheetName", "print-to-Excel uses named sheets");
  has("src/utils/exportPrintTables.ts", "data-export-autofilter-range", "single-sheet exports can scope AutoFilter to the data table");
  has("src/utils/exportPrintTables.ts", "data-export-freeze-row", "single-sheet exports can freeze the correct header row");
  has("src/utils/exportPrintTables.ts", "data-export-widths", "single-sheet exports declare readable column widths");
  has("src/utils/exportPrintTables.ts", '"!autofilter"', "print-to-Excel adds AutoFilter to data sheets");
  has("src/utils/exportPrintTables.ts", '"!views"', "print-to-Excel freezes data headers");
  has("src/utils/exportPrintTables.ts", "qualifyFormula", "summary formulas reference their source sheet");
  has("src/utils/exportPrintTables.ts", "data-v", "print-to-Excel reads raw numeric values");
  has("src/utils/exportPrintTables.ts", "data-f", "print-to-Excel writes formula cells");

  has("src/modules/warehouse/inventory/pages/InventoryPeriodReportPage.tsx", "buildPeriodReport(", "inventory print and Excel share one report definition");
  has("src/modules/warehouse/inventory/pages/InventoryPeriodReportPage.tsx", "exportTablesToExcel(document", "inventory Excel export uses the single-sheet print table");
  has("src/modules/warehouse/inventory/pages/InventoryPeriodReportPage.tsx", 'scope="filtered"', "inventory Excel export keeps its filtered scope");
  has("src/modules/warehouse/inventory/pages/InventoryPeriodReportPage.tsx", 'format="excel"', "inventory Excel export keeps its Excel format");
  assert.ok(!read("src/modules/warehouse/inventory/pages/InventoryPeriodReportPage.tsx").includes("XLSX.utils.book_new"), "inventory Excel no longer builds multiple sheets");
  has("src/utils/inventoryPrint.ts", "data-export-sheet=", "inventory print exports one named worksheet");
  has("src/utils/inventoryPrint.ts", "data-export-autofilter-range=", "inventory worksheet scopes AutoFilter to data rows");
  has("src/utils/inventoryPrint.ts", "data-export-freeze-row=", "inventory worksheet freezes the Excel header");
  has("src/utils/inventoryPrint.ts", "EXPORT SOURCE", "inventory worksheet keeps its audit trail on the same sheet");
  has("src/modules/warehouse/inventory/print/reports.ts", "excelWidths", "inventory reports declare readable column widths");

  for (const file of [
    "src/components/print/DocumentPrintTemplate.tsx",
    "src/components/print/FinancialReportPrintTemplate.tsx",
    "src/utils/inventoryPrint.ts",
    "src/modules/finance/general-ledger/GeneralLedgerPrintPage.tsx",
    "src/modules/finance/journals/JournalRegisterPrintPage.tsx",
    "src/modules/finance/trial-balance/TrialBalancePrintPage.tsx",
  ]) {
    assert.ok(!read(file).includes("Print preview uses"), `print output stays unchanged in ${file}`);
  }

  const routes = read("src/router/routes.tsx");
  for (const route of [
    'path: "general-ledger/print"',
    'path: "journal/register/print"',
    'path: "journal/trial-balance/print"',
    'path: "purchase-requisitions/:id/print"',
    'path: "market-lists/:id/print"',
    'path: "purchase-orders/:id/print"',
    'path: "receiving/:id/print"',
    'path: "accounts-payable/aging/print"',
  ]) {
    assert.ok(routes.includes(route), `print route preserved: ${route}`);
  }
  for (const kind of ["purchase-requisitions", "market-lists", "purchase-orders", "goods-receipts"]) {
    assert.ok(routes.includes(`kind="${kind}"`), `print kind preserved: ${kind}`);
  }
  for (const [file, kind] of [
    ["src/modules/purchasing/requisition/pages/PurchaseRequisitionListPage.tsx", "PURCHASE_REQUISITION_LIST"],
    ["src/modules/purchasing/market-list/MarketListPage.tsx", "MARKET_LIST_LIST"],
    ["src/modules/purchasing/purchase-order/pages/PurchaseOrderListPage.tsx", "PURCHASE_ORDER_LIST"],
    ["src/modules/purchasing/goods-receipts/pages/ReceivingPage.tsx", "GOODS_RECEIPT_LIST"],
    ["src/modules/purchasing/reports/PurchasingReportsPage.tsx", "PURCHASING_REPORT"],
  ]) {
    has(file, `kind="${kind}"`, "purchasing print tracking kind is preserved");
  }

  has("src/components/print/DocumentPrintTemplate.tsx", 'aria-label="Print document"', "document print action is preserved");
  has("src/components/print/DocumentPrintTemplate.tsx", "Download PDF", "document PDF action is preserved");
  has(
    "src/components/print/InventoryPrintButton.tsx",
    "aria-label={`Print complete ${reportLabel.toLowerCase()} report`}",
    "complete inventory report print action is preserved",
  );
  has("src/modules/master/products/pages/ProductPage.tsx", '"Download XLS"', "item master XLS label is preserved");
  has("src/modules/finance/accounts-payable/APReportingPage.tsx", "current-page export available", "AP export scope wording is preserved");
  has("src/modules/finance/accounts-receivable/ARReportingPage.tsx", "current-page export available", "AR export scope wording is preserved");
  has("src/modules/finance/accounts-receivable/ARReportingPage.tsx", "Stage AR Excel", "AR staging entry is preserved");
  has("src/modules/finance/cash-flow/CashierPage.tsx", 'title: "Petty Cash Book"', "Petty Cash print output title is preserved");
  has("src/modules/finance/journals/JournalListPage.tsx", "difference_amount:differenceAmount", "journal filter print params are preserved");
  has("src/modules/finance/journals/JournalRegisterPrintPage.tsx", "difference_amount:", "journal print route reads the difference filter");

  has("docs/finance-accounting.md", "Export current page CSV", "finance guide documents page export scope");
  has("docs/finance-accounting.md", "Export all filtered rows", "finance guide documents filtered export scope");
  has("docs/finance-accounting.md", "Journal → Journal Register", "finance guide names the formal register");
  has("src/components/common/UsageGuide.tsx", 'title:"Export and Print"', "usage guide covers export and print scope");
  has("package.json", "scripts/test-print-export-clarity.cjs", "clarity test runs with the finance suite");

  console.log("Print/export clarity PASS: explicit scope, UI-only notes, preserved routes, kinds, templates and labels.");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
