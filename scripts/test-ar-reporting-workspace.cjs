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
  global.__arApi = {
    get: async (url, config) => {
      calls.push({ url, params: config?.params });
      return { data: { items: [], total_items: 0, total_pages: 0 } };
    },
  };

  const bundle = await req("esbuild").build({
    absWorkingDir: root,
    tsconfig: root + "/tsconfig.app.json",
    entryPoints: ["src/modules/finance/accounts-receivable/reportingApi.ts"],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    plugins: [{
      name: "ar-api-mock",
      setup(build) {
        build.onResolve({ filter: /^@\/api\/interceptor$/ }, (args) => ({ path: args.path, namespace: "ar-api" }));
        build.onLoad({ filter: /.*/, namespace: "ar-api" }, () => ({
          contents: "export default globalThis.__arApi;",
          loader: "js",
        }));
      },
    }],
  });
  const module = { exports: {} };
  new Function("module", "exports", "require", bundle.outputFiles[0].text)(module, module.exports, (name) => req(name));
  const { arReportingApi } = module.exports;

  await arReportingApi.summary(2, 50, "  hotel  ");
  await arReportingApi.detail(3, 100, "invoice-1", "PARTIALLY_PAID");
  await arReportingApi.aging(1, 50, "");

  assert.equal(calls[0].url, "/ar-reporting/summary");
  assert.deepEqual(calls[0].params, { page: 2, page_size: 50, search: "hotel", status: undefined });
  assert.equal(calls[1].url, "/ar-reporting/detail");
  assert.deepEqual(calls[1].params, {
    page: 3,
    page_size: 100,
    search: "invoice-1",
    status: "PARTIALLY_PAID",
  });
  assert.equal(calls[2].url, "/ar-reporting/aging");
  assert.deepEqual(calls[2].params, { page: 1, page_size: 50, search: undefined, status: undefined });

  const page = read("src/modules/finance/accounts-receivable/ARReportingPage.tsx");
  assert.ok(page.includes('<DataWorkspace area="Accounting" className="data-first">'), "AR uses the finance data-first shell");
  assert.equal((page.match(/<PageHeader/g) ?? []).length, 1, "AR has one page header");
  assert.ok(page.includes("<ModuleSummary"), "AR has a shared summary strip");
  assert.ok(page.includes("ListToolbar"), "AR uses the shared list toolbar");
  assert.ok(page.includes("shared Pagination") || page.includes("<Pagination"), "AR uses shared pagination");
  assert.ok(page.includes("<ARWorkspaceHeader />"), "AR keeps its workspace tabs");
  assert.ok(!page.includes("ModuleWorkspaceHeader"), "AR does not duplicate a module heading");
  assert.ok(page.includes('value="PARTIALLY_PAID"') === false, "status options come from statusLabel");
  assert.ok(page.includes('PARTIALLY_PAID: "Partially Paid"'), "reported partial status label is preserved");
  assert.ok(page.includes("Stage AR Excel"), "AR staging entry stays available");
  assert.ok(page.includes("current-page export available"), "export scope is stated to users");

  const header = read("src/modules/finance/accounts-receivable/ARWorkspaceHeader.tsx");
  assert.ok(!header.includes("ModuleWorkspaceHeader"), "AR workspace header is tabs only");
  for (const tab of [
    'to: "/accounts-receivable"',
    'to: "/accounts-receivable/detail"',
    'to: "/accounts-receivable/aging"',
  ]) {
    assert.ok(header.includes(tab), `AR workspace keeps ${tab}`);
  }

  const receipt = read("src/modules/finance/accounts-receivable/ARReceiptForm.tsx");
  assert.ok(receipt.includes("todayLocal()"), "receipt date defaults to the local business date");
  assert.ok(receipt.includes("Receipt cannot exceed the outstanding balance."), "overpayment is blocked before submit");
  assert.ok(receipt.includes("idempotency_key: input.requestKey"), "receipt retry key payload is preserved");
  assert.ok(receipt.includes("recovery.notifyRestored()"), "restored receipt input is announced");

  const routes = read("src/router/routes.tsx");
  for (const route of [
    'path: "accounts-receivable"',
    'path: "accounts-receivable/detail"',
    'path: "accounts-receivable/aging"',
  ]) {
    assert.ok(routes.includes(route), `AR route preserved: ${route}`);
  }

  console.log("AR reporting workspace PASS: data-first tabs, backend status filter, receipt guard, preserved routes.");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
