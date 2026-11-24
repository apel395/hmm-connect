/* global require, __dirname, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const req = require("node:module").createRequire(root + "/package.json");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");

async function run() {
  const bundle = await req("esbuild").build({
    absWorkingDir: root,
    tsconfig: root + "/tsconfig.app.json",
    entryPoints: ["src/components/navigation/navigationConfig.ts"],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    external: ["react", "react/jsx-runtime"],
  });
  const module = { exports: {} };
  new Function("module", "exports", "require", bundle.outputFiles[0].text)(module, module.exports, (name) => req(name));
  const { visibleNavigation, activeNavigation, navigationGroups } = module.exports;

  const financeUser = { roles: [{ name: "FINANCE", permissions: [{ code: "finance.view" }] }] };
  const financePaths = visibleNavigation(financeUser)
    .flatMap((group) => group.children ?? [group])
    .map((child) => child.url);

  assert.ok(financePaths.includes("/cash-bank/petty-cash"), "petty cash remains in Finance navigation");
  assert.ok(!financePaths.includes("/cash-bank/cashier"), "general cashier is removed from Finance navigation");

  const active = activeNavigation(navigationGroups, "/cash-bank/petty-cash", "");
  assert.equal(active?.child?.title, "Petty Cash", "petty cash route maps to the Petty Cash child");

  const routes = read("src/router/routes.tsx");
  assert.ok(routes.includes('<Navigate to="/cash-bank/petty-cash" replace />'), "legacy cashier route redirects to petty cash");
  assert.ok(!routes.includes("<CashierPage petty />"), "the old petty prop is no longer used");

  const workspace = read("src/modules/finance/cash-flow/CashBankWorkspacePage.tsx");
  assert.ok(!workspace.includes("General Cashier"), "workspace tabs no longer expose General Cashier");
  assert.ok(workspace.includes('label: "Petty Cash"'), "workspace keeps the Petty Cash tab");

  const page = read("src/modules/finance/cash-flow/CashierPage.tsx");
  assert.ok(page.includes("petty_cash: true"), "page still uses the backend petty filter");
  assert.ok(page.includes('title: "Petty Cash Book"'), "print output is Petty Cash Book");
  assert.ok(page.includes("currentMonth"), "default period is the current month");
  assert.ok(!page.includes("General Cashier"), "page has no General Cashier labels");

  const titles = read("src/components/workspace/workspaceTitle.ts");
  assert.ok(titles.includes('"/cash-bank/petty-cash": "Petty Cash"'), "browser title is stable for Petty Cash");

  const docs = read("docs/finance-accounting.md");
  assert.ok(docs.includes("General Cashier tidak ditampilkan lagi"), "finance guide documents the removed entry");

  console.log("Petty cash workspace PASS: General Cashier hidden, legacy route redirected, Petty view restored.");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
