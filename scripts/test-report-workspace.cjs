/* global require, __dirname, console */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
const has = (source, tokens, label) => {
  for (const token of tokens) {
    assert.ok(source.includes(token), `${label}: missing ${JSON.stringify(token)}`);
  }
};

const shared = read("src/modules/finance/financial-statements/FinancialReportPage.tsx");
has(shared, [
  '<DataWorkspace area="Reports"',
  "ModuleSummary",
  "Loading",
  "Empty",
  "apiErrorMessage",
  "FORM_UI",
], "Balance Sheet / P&L shared workspace shell");

has(shared, [
  '"/financial-reports/comparison"',
  '"/financial-reports/comparison/export"',
  '["financial-report-comparison", kind, applied]',
  "PrintPreviewButton",
  "ReportUnitButtons",
  '"MTD"',
  '"YTD"',
], "report API, print and period contracts");

has(shared, [
  '"PROFIT_LOSS"',
  '"BALANCE_SHEET"',
  "presentation_rows",
  "BalanceStatus",
  "loadReportPreferences",
  "saveReportPreferences",
], "Balance Sheet and P&L behavior preserved");

const routes = read("src/router/routes.tsx");
has(routes, ['path: "balance-sheet"', 'path: "profit-loss"', 'path: "balance-sheet/print"', 'path: "profit-loss/print"'], "report routes preserved");

console.log("Report workspace PASS: shared states, preserved report API, print scopes and period controls.");
