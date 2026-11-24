/* global require, __dirname, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const req = require("node:module").createRequire(root + "/package.json");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

async function run() {
  const shared = read("src/modules/finance/types.ts");
  assert.ok(shared.includes("export type FinancePage<T>"), "shared pagination envelope is exported");
  assert.ok(shared.includes("export type FinanceAllowedActions"), "shared capability contract is exported");
  assert.ok(shared.includes("PARTIAL: \"PARTIALLY_PAID\""), "raw PARTIAL normalizes to reported PARTIALLY_PAID");
  assert.ok(shared.includes("export type AgingBucket"), "shared aging buckets are exported");

  const compiled = await req("esbuild").build({
    absWorkingDir: root,
    tsconfig: root + "/tsconfig.app.json",
    entryPoints: ["src/modules/finance/types.ts"],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
  });
  const typesModule = { exports: {} };
  new Function("module", "exports", "require", compiled.outputFiles[0].text)(
    typesModule,
    typesModule.exports,
    (name) => req(name),
  );
  const { reportedPaymentStatus, financePageParams } = typesModule.exports;
  assert.equal(reportedPaymentStatus("PARTIAL"), "PARTIALLY_PAID", "raw PARTIAL maps to reported status");
  assert.equal(reportedPaymentStatus("partially_paid"), "PARTIALLY_PAID", "case is normalized");
  assert.equal(reportedPaymentStatus("UNKNOWN"), "UNPAID", "unknown status falls back safely");
  assert.deepEqual(
    financePageParams({ page: 2, pageSize: 100, search: "  hotel ", status: undefined }),
    { page: 2, page_size: 100, search: "hotel", status: undefined },
    "page params keep backend names",
  );

  const voucherApi = read("src/modules/finance/payment-vouchers/api.ts");
  assert.ok(voucherApi.includes("FinancePage<Voucher>"), "voucher list uses the shared page type");
  assert.ok(voucherApi.includes("rejectVoucher = async (id: number, reason: string)"), "reject reason is required");
  assert.ok(!voucherApi.includes("Record<string, any>"), "voucher API has no untyped record");

  const invoiceApi = read("src/modules/finance/supplier-invoices/api.ts");
  assert.ok(invoiceApi.includes("FinancePage<SupplierInvoice>"), "invoice list uses the shared page type");
  assert.ok(invoiceApi.includes("export type InvoiceAction"), "invoice actions are enumerated");
  assert.ok(!invoiceApi.includes("params: any"), "invoice query params are typed");

  const paymentApi = read("src/modules/finance/payments/api.ts");
  assert.ok(paymentApi.includes("FinancePage<Payment>"), "payment list uses the shared page type");
  assert.ok(paymentApi.includes("export type PaymentAction"), "payment actions are enumerated");
  assert.ok(!paymentApi.includes("params: any"), "payment query params are typed");
  assert.ok(!paymentApi.includes("payload: any"), "payment payload is typed");
  assert.ok(!paymentApi.includes("allocations: any[]"), "payment allocations are typed");
  assert.ok(!paymentApi.includes("funding_lines: any[]"), "payment funding lines are typed");

  const cashApi = read("src/modules/finance/cash-flow/api.ts");
  assert.ok(cashApi.includes("export type CashFlowQuery"), "cash-flow query params are typed");
  assert.ok(!cashApi.includes("params:any"), "cash-flow API has no untyped params");

  for (const file of [
    "src/modules/finance/accounts-payable/reportingApi.ts",
    "src/modules/finance/accounts-receivable/reportingApi.ts",
  ]) {
    assert.ok(read(file).includes("FinancePage<"), `${file} uses the shared page type`);
  }

  const hook = read("src/modules/finance/hooks/useFinanceList.ts");
  assert.ok(hook.includes("export function useFinancePagination"), "shared pagination hook is exported");
  assert.ok(hook.includes("export function useFinanceList"), "shared list hook is exported");
  assert.ok(hook.includes("page_size: pagination.pageSize"), "hook sends backend page_size");

  for (const file of [
    "src/modules/finance/accounts-payable/APReportingPage.tsx",
    "src/modules/finance/accounts-receivable/ARReportingPage.tsx",
    "src/modules/finance/supplier-invoices/SupplierInvoiceListPage.tsx",
    "src/modules/finance/payments/PaymentListPage.tsx",
    "src/modules/finance/payment-vouchers/pages/PaymentVoucherListPage.tsx",
  ]) {
    assert.ok(read(file).includes("useFinanceList"), `${file} adopts the shared list hook`);
  }

  const typeTest = read("src/modules/finance/contracts.type-test.ts");
  assert.ok(
    (typeTest.match(/@ts-expect-error/g) ?? []).length >= 7,
    "type-level contract regressions are asserted",
  );

  console.log("Finance contracts PASS: typed APIs, shared list hooks, raw/reported status, compile-time guards.");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
