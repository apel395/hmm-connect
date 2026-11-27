/* global require, __dirname, console, global, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const req = require("node:module").createRequire(root + "/package.json");
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

const arReport = read("src/modules/finance/accounts-receivable/ARReportingPage.tsx");
has(arReport, [
  "PageHeader",
  '<DataWorkspace area="Accounting"',
  "ModuleSummary",
  "Loading",
  "Empty",
  "apiErrorMessage",
  "Badge",
  "ListToolbar",
  "<Pagination",
  "<ARWorkspaceHeader />",
], "AR reporting shared workspace shell");
has(arReport, [
  'queryKey: ["ar-reporting", "detail"]',
  "arReportingApi.summary",
  "arReportingApi.aging",
  "exportCsv(",
  "Stage AR Excel",
  "current-page export available",
], "AR reporting API and export contracts preserved");

const apReport = read("src/modules/finance/accounts-payable/APReportingPage.tsx");
has(apReport, [
  "PageHeader",
  '<DataWorkspace area="Accounting"',
  "ModuleSummary",
  "Loading",
  "Empty",
  "apiErrorMessage",
  "Badge",
  "ReportUnitButtons",
  "ListToolbar",
  "<Pagination",
  "<APWorkspaceHeader />",
], "AP reporting shared workspace shell");
has(apReport, [
  'queryKey: ["ap-reporting", "summary"',
  "apReportingApi.detail",
  "exportCsv(",
  "View Aging",
  "current-page export available",
], "AP reporting API and export contracts preserved");

const apAging = read("src/modules/finance/accounts-payable/AccountsPayablePage.tsx");
has(apAging, [
  "PageHeader",
  '<DataWorkspace area="Accounting"',
  "ModuleSummary",
  "Loading",
  "Empty",
  "apiErrorMessage",
  "Badge",
  '<APWorkspaceHeader />',
  'src={printSrc}',
  'aria-label="Invoice date from"',
  'aria-label="Invoice date to"',
  "opening_unassigned",
  "Aging Buckets",
  "Invoice Payment History",
], "AP aging shared workspace shell and preserved views");

const fiscalHeader = read("src/modules/finance/fiscal/FiscalWorkspaceHeader.tsx");
has(fiscalHeader, [
  '<nav className="flex min-w-max gap-6 overflow-x-auto border-b border-slate-200" aria-label="Fiscal workspace">',
  'label: "COA & Mapping"',
  'label: "Reconciliation"',
  'label: "Lampiran 1D"',
  'label: "SPT Tahunan 1771"',
], "Fiscal workspace tabs preserved");
assert.ok(!fiscalHeader.includes("ModuleWorkspaceHeader"), "Fiscal header no longer duplicates the page heading");

const fiscalAccount = read("src/modules/finance/fiscal/pages/FiscalAccountPage.tsx");
has(fiscalAccount, [
  '<DataWorkspace area="Accounting"',
  "FiscalWorkspaceHeader",
  "PageHeader",
  "ModuleSummary",
  "Loading",
  "Empty",
  "apiErrorMessage",
  "Badge",
  'scope="page" format="csv"',
  'queryKey: ["fiscal-linked", params]',
  "fiscalApi.linkedCoa(params)",
  "fiscalApi.createMapping",
  "fiscalApi.deleteMapping",
  "window.print()",
], "Fiscal COA mapping shared shell and preserved behavior");

const fiscalReconciliation = read("src/modules/finance/fiscal/pages/FiscalReconciliationPage.tsx");
has(fiscalReconciliation, [
  '<DataWorkspace area="Accounting"',
  "FiscalWorkspaceHeader",
  "PageHeader",
  "ModuleSummary",
  "Loading",
  "No P&amp;L activity in the selected period.",
  "apiErrorMessage",
  "Badge",
  ") : query.isError ? (",
  'queryKey: ["fiscal-reconciliation", { dateFrom, dateTo }]',
  "fiscalApi.reconciliation",
  "have no fiscal mapping",
  "window.print()",
], "Fiscal reconciliation shared shell and preserved behavior");

const lampiran = read("src/modules/finance/fiscal/pages/Lampiran1DPage.tsx");
has(lampiran, [
  '<DataWorkspace area="Accounting" className="data-first print-document">',
  "FiscalWorkspaceHeader",
  "PageHeader",
  "ModuleSummary",
  "Loading",
  "No P&amp;L activity in the fiscal year.",
  "No fiscal balance sheet sections.",
  "apiErrorMessage",
  "Badge",
  "FORM_UI",
  "const loadError = recon.isError || balanceSheet.isError;",
  'scope="filtered" format="csv"',
  'queryKey: ["fiscal-lampiran-1d-recon"',
  'queryKey: ["fiscal-lampiran-1d-bs"',
  "fiscalApi.fiscalBalanceSheet",
  "Non-Taxable Object",
  "Lampiran 1D – Rekonsiliasi Laporan Keuangan (Jasa)",
], "Lampiran 1D shared shell and preserved report contract");
assert.ok(!lampiran.includes("!recon.data"), "Lampiran 1D does not treat an empty response as an error");

const spt = read("src/modules/finance/fiscal/pages/Spt1771Page.tsx");
has(spt, [
  '<DataWorkspace area="Accounting"',
  "FiscalWorkspaceHeader",
  "PageHeader",
  "ModuleSummary",
  "Loading",
  "Loading tax credits…",
  "apiErrorMessage",
  "Badge",
  "const isLoading = report.isLoading;",
  "report.isError &&",
  'queryKey: ["spt-1771", { taxYear, kompensasi }]',
  'queryKey: ["spt-1771-profile", taxYear]',
  'queryKey: ["spt-1771-credits", taxYear]',
  "fiscalApi.sptUpsertProfile",
  "fiscalApi.sptCreateCredit",
  "fiscalApi.sptDeleteCredit",
  "No tax credits recorded",
  "window.print()",
], "SPT 1771 shared shell and preserved report contract");
assert.ok(!spt.includes("profileQuery.isLoading ||"), "SPT profile editing is not blocked by slow companion queries");

const fiscalApiSource = read("src/modules/finance/fiscal/api.ts");
has(fiscalApiSource, [
  "api.get<FiscalAccountPage>(",
  "api.get<FiscalLinkedAccountPage>(",
  "api.get<FiscalReconciliationResponse>(",
  "api.get<FiscalBalanceSheetResponse>(",
  "api.get<Spt1771Response>(",
  "api.get<TaxCredit[]>(",
  "FiscalUnmappedCommercialResponse",
  "counterparty_npwp?: string | null",
], "Fiscal API responses are typed");
assert.ok(!fiscalApiSource.includes(": any"), "Fiscal API has no untyped values");

const routes = read("src/router/routes.tsx");
has(routes, [
  'path: "balance-sheet"',
  'path: "profit-loss"',
  'path: "balance-sheet/print"',
  'path: "profit-loss/print"',
  'path: "general-ledger"',
  'path: "general-ledger/print"',
  'path: "journal/trial-balance/print"',
  'path: "accounts-receivable"',
  'path: "accounts-receivable/detail"',
  'path: "accounts-receivable/aging"',
  'path: "accounts-payable"',
  'path: "accounts-payable/detail"',
  'path: "accounts-payable/aging"',
  'path: "accounts-payable/aging/print"',
  'path: "finance/fiscal/coa"',
  'path: "finance/fiscal/reconciliation"',
  'path: "finance/fiscal/lampiran-1d"',
  'path: "finance/fiscal/spt-1771"',
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
  ["src/modules/finance/accounts-payable/APAgingPrintPage.tsx", "AP aging print", [
    '["accounts-payable-aging", "print"]',
    'api.get<AgingPrintResponse>("/ap-aging/print")',
    'data-print-ready="false"',
    'data-print-ready="true"',
    "Loading",
    "Empty",
    "apiErrorMessage",
    "ACCOUNT PAYABLE AGING",
    ">TOTAL<",
  ]],
];
for (const [file, label, tokens] of printPages) has(read(file), tokens, label);

async function checkFiscalApiContracts() {
  const calls = [];
  global.__fiscalApi = {
    get: async (url, config) => {
      calls.push({ method: "get", url, params: config?.params });
      return { data: { items: [], total: 0, page: 1, page_size: 25, pages: 1 } };
    },
    post: async (url, data, config) => {
      calls.push({ method: "post", url, data, params: config?.params });
      return { data: {} };
    },
    put: async (url, data, config) => {
      calls.push({ method: "put", url, data, params: config?.params });
      return { data: {} };
    },
    delete: async (url, config) => {
      calls.push({ method: "delete", url, params: config?.params });
      return { data: {} };
    },
  };

  const bundle = await req("esbuild").build({
    absWorkingDir: root,
    tsconfig: root + "/tsconfig.app.json",
    entryPoints: ["src/modules/finance/fiscal/api.ts"],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    plugins: [{
      name: "fiscal-api-mock",
      setup(build) {
        build.onResolve({ filter: /^@\/api\/client$/ }, () => ({ path: "fiscal-api", namespace: "fiscal-api" }));
        build.onLoad({ filter: /.*/, namespace: "fiscal-api" }, () => ({
          contents: "export default globalThis.__fiscalApi;",
          loader: "js",
        }));
      },
    }],
  });
  const apiModule = { exports: {} };
  new Function("module", "exports", "require", bundle.outputFiles[0].text)(
    apiModule,
    apiModule.exports,
    (name) => req(name),
  );
  const { fiscalApi } = apiModule.exports;

  await fiscalApi.accounts({ page: 2, page_size: 50, is_header: false });
  await fiscalApi.linkedCoa({ status: "linked", search: "hotel" });
  await fiscalApi.reconciliation({ date_from: "2026-01-01", date_to: "2026-12-31", location_id: 8 });
  await fiscalApi.fiscalBalanceSheet({ fiscal_year: 2026, department_id: 7 });
  await fiscalApi.sptReport({ tax_year: 2026, kompensasi_kerugian: 1000 });
  await fiscalApi.sptProfile(2026);
  await fiscalApi.sptUpsertProfile(2026, { npwp: "123" });
  await fiscalApi.sptCredits(2026);
  await fiscalApi.sptCreateCredit({ tax_year: 2026, credit_type: "PPh 25", amount: 100 });
  await fiscalApi.sptDeleteCredit(9);

  assert.deepEqual(calls, [
    { method: "get", url: "/fiscal/accounts", params: { page: 2, page_size: 50, is_header: false } },
    { method: "get", url: "/fiscal/linked-coa", params: { status: "linked", search: "hotel" } },
    { method: "get", url: "/fiscal/reconciliation", params: { date_from: "2026-01-01", date_to: "2026-12-31", location_id: 8 } },
    { method: "get", url: "/fiscal-balance-sheet", params: { fiscal_year: 2026, department_id: 7 } },
    { method: "get", url: "/spt-1771/report", params: { tax_year: 2026, kompensasi_kerugian: 1000 } },
    { method: "get", url: "/spt-1771/profile", params: { tax_year: 2026 } },
    { method: "put", url: "/spt-1771/profile", data: { npwp: "123" }, params: { tax_year: 2026 } },
    { method: "get", url: "/spt-1771/credits", params: { tax_year: 2026 } },
    { method: "post", url: "/spt-1771/credits", data: { tax_year: 2026, credit_type: "PPh 25", amount: 100 }, params: undefined },
    { method: "delete", url: "/spt-1771/credits/9", params: undefined },
  ], "fiscal API endpoints and parameters are preserved");
  assert.ok(calls.every((call) => !("database" in (call.params ?? {}))), "fiscal API never sends a client database selector");
}

checkFiscalApiContracts()
  .then(() => console.log("Report workspace PASS: shared states, preserved report API, print scopes and period controls."))
  .catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
