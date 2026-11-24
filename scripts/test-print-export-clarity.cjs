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
