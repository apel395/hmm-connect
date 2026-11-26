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

const trial = read("src/modules/finance/trial-balance/TrialBalancePage.tsx");
has(trial, [
  "PageHeader",
  '<DataWorkspace area="Accounting"',
  "WorkspaceFilters",
  "ModuleSummary",
  "Loading",
  "Empty",
  "apiErrorMessage",
  "FORM_UI",
  "Badge",
], "Trial Balance shared workspace shell");
has(trial, [
  '["trial-balance", filters]',
  'scope="filtered" format="excel"',
  "note={GENERIC_REPORT_PRINT_NOTE}",
  "/journal/trial-balance/print",
  'queryKey: ["trial-balance-locations"',
  'queryKey: ["report-units"]',
], "Trial Balance query, export and print contracts preserved");
has(read("src/modules/finance/trial-balance/api.ts"), [
  "export interface TrialBalanceFilters",
  "export interface TrialBalanceRow",
  "export interface TrialBalanceResponse",
  'api.get<TrialBalanceResponse>("/trial-balance"',
], "Trial Balance typed contracts preserved");

const ledger = read("src/modules/finance/general-ledger/GeneralLedgerPage.tsx");
has(ledger, [
  "PageHeader",
  '<DataWorkspace area="Accounting"',
  "ModuleSummary",
  "Badge",
  "Loading",
  "Empty",
  "apiErrorMessage",
  'queryKey: ["general-ledger", params]',
  'queryKey: ["general-ledger-grouped"',
  "printSrc = `/general-ledger/print",
], "General Ledger shared workspace shell");
has(ledger, [
  'scope="filtered" format="excel"',
  "PrintPreviewButton src={printSrc}",
  ".gl-ledger-viewport",
  "workspace-ledger-table",
  "groupByAccount",
  "Adjust filters",
  "Retry",
], "General Ledger print, export and interaction contracts preserved");

const ledgerApi = read("src/modules/finance/general-ledger/api.ts");
has(ledgerApi, [
  "export type LedgerListParams",
  "export interface LedgerEntry",
  "export interface LedgerListResponse",
  "export interface LedgerPrintResponse",
  "export interface ExportJobStatus",
  'api.get<LedgerListResponse>("/general-ledger"',
  'api.get<LedgerPrintResponse>("/general-ledger/print"',
  'api.post<LedgerExportJob>("/exports"',
  'api.get<ExportJobStatus>(`/exports/${jobId}`)',
  'export_type: "general_ledger"',
], "General Ledger typed contracts and endpoints preserved");
assert.ok(!ledgerApi.includes(": any"), "General Ledger API has no untyped values");

const routes = read("src/router/routes.tsx");
has(routes, [
  'path: "balance-sheet"',
  'path: "profit-loss"',
  'path: "balance-sheet/print"',
  'path: "profit-loss/print"',
  'path: "general-ledger"',
  'path: "general-ledger/print"',
  'path: "journal/trial-balance/print"',
], "report routes preserved");

const printPages = [
  ["src/modules/finance/financial-statements/FinancialReportPrintPage.tsx", "financial-statement print", [
    "data-print-ready=\"false\"",
    "data-print-ready=\"true\"",
    "Loading",
    "Empty",
    "apiErrorMessage",
    '"/financial-reports/comparison"',
  ]],
  ["src/modules/finance/trial-balance/TrialBalancePrintPage.tsx", "Trial Balance print", [
    '["trial-balance-print", params]',
    "FinancialReportPrintTemplate",
    "Loading",
    "Empty",
    "apiErrorMessage",
  ]],
  ["src/modules/finance/general-ledger/GeneralLedgerPrintPage.tsx", "General Ledger print", [
    '["general-ledger", "print", params]',
    "getLedgerPrint",
    "Loading",
    "Empty",
    "apiErrorMessage",
  ]],
];
for (const [file, label, tokens] of printPages) has(read(file), tokens, label);

console.log("Report workspace PASS: shared states, preserved report API, print scopes and period controls.");
