/* global require, __dirname, console, process, global */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const req = require("node:module").createRequire(root + "/package.json");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

async function run() {
  const calls = [];
  global.__apApi = {
    get: async (url, config) => {
      calls.push({ url, params: config?.params });
      return { data: { items: [], total_items: 0, total_pages: 0 } };
    },
  };

  const bundle = await req("esbuild").build({
    absWorkingDir: root,
    tsconfig: root + "/tsconfig.app.json",
    entryPoints: ["src/modules/finance/accounts-payable/reportingApi.ts"],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    plugins: [{
      name: "ap-api-mock",
      setup(build) {
        build.onResolve({ filter: /^@\/api\/interceptor$/ }, (args) => ({ path: args.path, namespace: "ap-api" }));
        build.onLoad({ filter: /.*/, namespace: "ap-api" }, () => ({
          contents: "export default globalThis.__apApi;",
          loader: "js",
        }));
      },
    }],
  });
  const apiModule = { exports: {} };
  new Function("module", "exports", "require", bundle.outputFiles[0].text)(apiModule, apiModule.exports, (name) => req(name));
  const { apReportingApi } = apiModule.exports;

  await apReportingApi.summary({ page: 2, pageSize: 50, search: "  hotel  ", businessUnitId: 3 });
  await apReportingApi.detail({ page: 3, pageSize: 100, search: "invoice-1", status: "PARTIALLY_PAID" });

  assert.equal(calls[0].url, "/ap-reporting/summary");
  assert.deepEqual(calls[0].params, {
    page: 2,
    page_size: 50,
    business_unit_id: 3,
    search: "hotel",
    status: undefined,
  });
  assert.equal(calls[1].url, "/ap-reporting/detail");
  assert.deepEqual(calls[1].params, {
    page: 3,
    page_size: 100,
    business_unit_id: undefined,
    search: "invoice-1",
    status: "PARTIALLY_PAID",
  });

  const reporting = read("src/modules/finance/accounts-payable/APReportingPage.tsx");
  assert.ok(reporting.includes('<DataWorkspace area="Accounting" className="data-first">'), "AP uses the finance data-first shell");
  assert.equal((reporting.match(/<PageHeader/g) ?? []).length, 1, "AP reporting has one page header");
  assert.ok(reporting.includes("<ModuleSummary"), "AP reporting has a shared summary strip");
  assert.ok(reporting.includes("ListToolbar"), "AP reporting uses the shared list toolbar");
  assert.ok(reporting.includes("<Pagination"), "AP reporting uses shared pagination");
  assert.ok(reporting.includes("<APWorkspaceHeader />"), "AP reporting keeps workspace tabs");
  assert.ok(!reporting.includes("ModuleWorkspaceHeader"), "AP reporting does not duplicate a module heading");
  assert.ok(reporting.includes('PARTIALLY_PAID: "Partially Paid"'), "reported partial status label is preserved");
  assert.ok(reporting.includes("status: status === \"ALL\" ? undefined : status"), "status filter only reaches supported detail endpoint");
  assert.ok(reporting.includes("current-page export available"), "export scope is stated to users");

  const header = read("src/modules/finance/accounts-payable/APWorkspaceHeader.tsx");
  assert.ok(!header.includes("ModuleWorkspaceHeader"), "AP workspace header is tabs only");
  for (const tab of [
    'to: "/accounts-payable"',
    'to: "/accounts-payable/detail"',
    'to: "/accounts-payable/aging"',
    'to: "/accounts-payable/movement"',
    'to: "/finance/payment-vouchers"',
  ]) {
    assert.ok(header.includes(tab), `AP workspace keeps ${tab}`);
  }

  const aging = read("src/modules/finance/accounts-payable/AccountsPayablePage.tsx");
  assert.equal((aging.match(/<PageHeader/g) ?? []).length, 1, "AP aging has one page header");
  assert.ok(aging.includes('src="/accounts-payable/aging/print"'), "AP aging print route is preserved");
  assert.ok(aging.includes("opening_unassigned"), "manual opening AP exception stays visible");

  const movement = read("src/modules/finance/accounts-payable/APMovementPage.tsx");
  assert.equal((movement.match(/<PageHeader/g) ?? []).length, 1, "AP movement has one page header");
  assert.ok(movement.includes("<APWorkspaceHeader />"), "AP movement keeps workspace tabs");
  assert.ok(!movement.includes("<CardTitle className=\"text-sm\">AP Movement</CardTitle>"), "AP movement heading is not duplicated");

  const invoiceList = read("src/modules/finance/supplier-invoices/SupplierInvoiceListPage.tsx");
  assert.ok(invoiceList.includes("<ModuleSummary"), "supplier invoice metrics use the shared strip");
  assert.ok(invoiceList.includes("ListToolbar"), "supplier invoice filters use the shared toolbar");
  assert.ok(invoiceList.includes("<Pagination"), "supplier invoices use shared pagination");
  assert.ok(invoiceList.includes("Confirm whether the supplier invoice records PPN."), "PPN confirmation is preserved");
  assert.ok(invoiceList.includes("Faktur Pajak Number is required for an invoice with PPN."), "faktur guard is preserved");
  assert.ok(invoiceList.includes("Document Total does not match the recalculated Invoice Total"), "document-total guard is preserved");
  assert.ok(invoiceList.includes("withSyncedDocumentTotal"), "stale-total sync is preserved");

  const voucherDetail = read("src/modules/finance/payment-vouchers/pages/PaymentVoucherDetailPage.tsx");
  for (const action of ["can_submit", "can_approve", "can_reject", "can_void", "can_print"]) {
    assert.ok(voucherDetail.includes(action), `voucher detail honours backend ${action}`);
  }
  assert.ok(voucherDetail.includes("<RejectDialog"), "voucher rejection collects a real reason");
  assert.ok(voucherDetail.includes("onReject={async (reason)"), "voucher rejection passes the dialog reason");
  assert.ok(voucherDetail.includes("rejectVoucher(voucherId, reason)"), "voucher rejection sends { reason } through the API");
  assert.ok(!voucherDetail.includes("Rejected from detail"), "hard-coded rejection reason is removed");
  assert.ok(voucherDetail.includes("no GL posting from vouchers"), "voucher/no-GL wording is clear");

  const voucherList = read("src/modules/finance/payment-vouchers/pages/PaymentVoucherListPage.tsx");
  assert.ok(voucherList.includes("<APWorkspaceHeader />"), "voucher list keeps AP tabs");
  assert.ok(voucherList.includes("do not post to the GL"), "voucher list repeats the approval-only contract");

  const payments = read("src/modules/finance/payments/PaymentListPage.tsx");
  assert.ok(payments.includes("Approve + Draft Journal"), "combined approval action is clearly labelled");
  assert.ok(payments.includes('approve: "Approve and create a draft journal"'), "confirmation still names both steps");
  assert.ok(payments.includes("<ListToolbar"), "payment filters use the shared toolbar");
  assert.ok(payments.includes("<ModuleSummary"), "payment metrics use the shared strip");
  assert.ok(payments.includes("<Pagination"), "payments use shared pagination");

  const navigation = await req("esbuild").build({
    absWorkingDir: root,
    tsconfig: root + "/tsconfig.app.json",
    entryPoints: ["src/components/navigation/navigationConfig.ts"],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    external: ["react", "react/jsx-runtime"],
  });
  const navModule = { exports: {} };
  new Function("module", "exports", "require", navigation.outputFiles[0].text)(navModule, navModule.exports, (name) => req(name));
  const { activeNavigation, navigationGroups } = navModule.exports;
  assert.equal(activeNavigation(navigationGroups, "/finance/payment-vouchers", "")?.child?.title, "Accounts Payable", "voucher route maps to AP navigation");
  assert.equal(activeNavigation(navigationGroups, "/payment-vouchers", "")?.child?.title, "Accounts Payable", "legacy voucher alias maps to AP navigation");
  const purchasing = navigationGroups.find((group) => group.title === "Purchasing");
  assert.equal(purchasing?.children?.length, 4, "purchasing navigation still has exactly four links");

  const routes = read("src/router/routes.tsx");
  for (const route of [
    'path: "accounts-payable"',
    'path: "accounts-payable/detail"',
    'path: "accounts-payable/aging"',
    'path: "accounts-payable/aging/print"',
    'path: "accounts-payable/movement"',
    'path: "finance/payment-vouchers"',
    'path: "finance/payment-vouchers/:id/print"',
    'path: "general-ledger/print"',
    'path: "journal/register/print"',
    'path: "journal/trial-balance/print"',
    'path: "purchase-requisitions/:id/print"',
    'path: "market-lists/:id/print"',
    'path: "purchase-orders/:id/print"',
    'path: "receiving/:id/print"',
  ]) {
    assert.ok(routes.includes(route), `route preserved: ${route}`);
  }
  for (const kind of ["purchase-requisitions", "market-lists", "purchase-orders", "goods-receipts"]) {
    assert.ok(routes.includes(`kind="${kind}"`), `print kind preserved: ${kind}`);
  }

  const docs = read("docs/finance-accounting.md");
  assert.ok(docs.includes("Payment voucher mengikuti `allowed_actions`"), "AP guide documents backend voucher actions");
  assert.ok(docs.includes("dikirim sebagai `{ reason }`"), "AP guide documents the rejection payload");
  assert.ok(docs.includes("persetujuan juga membuat draft journal"), "AP guide documents the combined payment action");

  console.log("AP workspace PASS: data-first tabs, reporting params, voucher actions, rejection reason, preserved routes.");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
