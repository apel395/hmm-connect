/* global require, __dirname, console, process, global */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const req = require("node:module").createRequire(root + "/package.json");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
const has = (file, needle, message) =>
  assert.ok(read(file).includes(needle), `${message}: ${file} missing ${JSON.stringify(needle)}`);
const hasnt = (file, needle, message) =>
  assert.ok(!read(file).includes(needle), `${message}: ${file} unexpectedly contains ${JSON.stringify(needle)}`);

async function renderPutAway() {
  const result = await req("esbuild").build({
    absWorkingDir: root,
    entryPoints: ["src/modules/warehouse/put-away/pages/PutAwayPage.tsx"],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    jsx: "automatic",
    external: ["react", "react/jsx-runtime"],
    plugins: [{
      name: "fixtures",
      setup(builder) {
        builder.onResolve({ filter: /^@\// }, (args) => ({ path: args.path, namespace: "fixture" }));
        builder.onLoad({ filter: /.*/, namespace: "fixture" }, () => ({
          loader: "js",
          contents: "import React from 'react';export default p=>React.createElement('div',null,p.children,p.title,p.description);",
        }));
      },
    }],
  });
  const module = { exports: {} };
  new Function("require", "module", "exports", result.outputFiles[0].text)(req, module, module.exports);
  const React = req("react");
  const renderer = req("react-test-renderer");
  global.IS_REACT_ACT_ENVIRONMENT = true;
  let tree;
  await renderer.act(async () => {
    tree = renderer.create(React.createElement(module.exports.default));
  });
  const text = JSON.stringify(tree.toJSON());
  assert.ok(text.includes("Put Away is not available"), "Put Away route shows an explicit unavailable state");
  assert.ok(text.includes("goods receipt is posted"), "Put Away explains where stock is placed");
  await renderer.act(async () => tree.unmount());
}

async function run() {
  has("src/modules/warehouse/errors.ts", "export function warehouseErrorMessage", "shared warehouse error helper is exported");

  const opname = "src/modules/warehouse/stock-opname/";
  const requests = "src/modules/warehouse/store-request/";
  const returns = "src/modules/warehouse/inventory-returns/";

  for (const [label, file] of [
    ["Stock Opname", `${opname}StockOpnamePage.tsx`],
    ["Store Request", `${requests}StoreRequestPage.tsx`],
    ["Inventory Returns", `${returns}InventoryReturnsPage.tsx`],
  ]) {
    const source = read(file);
    for (const token of ["DataWorkspace", "WorkspaceFilters", "PageHeader", "ModuleSummary", "Loading", "Empty", "Badge", "FORM_UI"]) {
      assert.ok(source.includes(token), `${label} uses shared ${token}`);
    }
    assert.ok(source.includes("warehouseErrorMessage"), `${label} uses the shared error helper`);
  }

  has(`${opname}types.ts`, "export type StockOpnameListParams", "stock opname list params are typed");
  has(`${opname}api.ts`, "StockOpnameListParams", "stock opname API uses the typed params");
  hasnt(`${opname}api.ts`, "Record<string, unknown>", "stock opname list params are not an untyped record");
  has(`${opname}StockOpnameDetailPage.tsx`, "warehouseErrorMessage", "opname detail uses shared errors");
  has(`${opname}StockOpnamePage.tsx`, '["stock-opnames"', "opname list query key is preserved");

  has(`${requests}types.ts`, "StoreRequestList", "store request list response is typed");
  has(`${requests}api.ts`, "api.get<StoreRequestList>", "store request list API is typed");
  hasnt(`${requests}StoreRequestPage.tsx`, "payload: any", "store request page has no untyped list payload");
  hasnt(`${requests}StoreRequestDetailPage.tsx`, "error: any", "store request detail has no untyped error");
  has(`${requests}StoreRequestPage.tsx`, '["store-requests"', "store request list query key is preserved");
  has(`${requests}api.ts`, "/store-requests/availability", "stock availability contract is preserved");

  has(`${returns}types.ts`, "ReturnDocument", "inventory return response types are shared");
  has(`${returns}InventoryReturnsPage.tsx`, "api.get<", "inventory return responses are typed");
  hasnt(`${returns}InventoryReturnsPage.tsx`, ": any", "inventory return page has no untyped values");
  hasnt(`${returns}ReturnCompletion.tsx`, ": any", "return completion has no untyped values");
  has(`${returns}InventoryReturnsPage.tsx`, '["inventory-returns"', "inventory return list query key is preserved");
  has(`${returns}InventoryReturnsPage.tsx`, "/credit", "supplier credit action is preserved");

  const putAway = "src/modules/warehouse/put-away/pages/PutAwayPage.tsx";
  has(putAway, "Put Away is not available", "dead Put Away endpoint fails closed");
  hasnt(putAway, "/put-away", "Put Away does not call the missing endpoint");
  assert.ok(!fs.existsSync(path.join(root, "src/modules/warehouse/put-away/api.ts")), "dead Put Away API is removed");
  assert.ok(!fs.existsSync(path.join(root, "src/modules/warehouse/put-away/usePutAway.ts")), "dead Put Away hook is removed");
  hasnt("src/modules/warehouse/inventory/print/reports.ts", '"putaway"', "dead Put Away print report is removed");

  const pkg = JSON.parse(read("package.json"));
  assert.ok(pkg.scripts["test:store-request"].includes("test-operational-flows.cjs"), "operational flow contract is registered");
  assert.ok(pkg.scripts.test.includes("test:store-request"), "operational flows run in npm test");

  await renderPutAway();
  console.log("Operational flows PASS: shared workspace shell, typed contracts, preserved keys and explicit Put Away unavailability.");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
