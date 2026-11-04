/* global require, __dirname, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");

const root = path.resolve(__dirname, "..");
const req = require("node:module").createRequire(path.join(root, "package.json"));

async function run() {
  const built = await req("esbuild").build({
    absWorkingDir: root,
    entryPoints: ["src/modules/warehouse/formDrafts.ts"],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
  });
  const module = { exports: {} };
  new Function("module", "exports", "require", built.outputFiles[0].text)(module, module.exports, req);
  const { validStockOpnameDraft, validStoreRequestDraft, validStockAdjustmentDraft } = module.exports;

  const opname = { warehouseId: 4, locationId: 2, departmentId: 3, notes: "Count freezer" };
  assert.equal(validStockOpnameDraft(opname), true);
  assert.equal(validStockOpnameDraft({ ...opname, warehouseId: "4" }), false);
  assert.equal(validStockOpnameDraft({ ...opname, notes: null }), false);

  const request = {
    requestDate: "2026-11-04", businessUnitId: 1, departmentId: 2,
    locationId: 3, warehouseId: 4, notes: "", items: [{ product_id: 99, quantity: 2.5 }],
  };
  assert.equal(validStoreRequestDraft(request), true);
  assert.equal(validStoreRequestDraft({ ...request, items: [{ quantity: "2" }] }), false);
  assert.equal(validStoreRequestDraft({ ...request, items: null }), false);

  const adjustment = {
    warehouseId: 4, adjustmentDate: "2026-11-04", reason: "Count correction", notes: "",
    lines: [{ key: 1, product_id: 99, system_quantity: 10, adjusted_quantity: 9, unit_cost: 5000, reason: "" }],
  };
  assert.equal(validStockAdjustmentDraft(adjustment), true);
  assert.equal(validStockAdjustmentDraft({ ...adjustment, lines: [{ ...adjustment.lines[0], system_quantity: "10" }] }), false);
  assert.equal(validStockAdjustmentDraft({ ...adjustment, lines: [{}] }), false);

  for (const file of [
    "stock-opname/StockOpnamePage.tsx",
    "store-request/StoreRequestPage.tsx",
    "inventory-adjustment/pages/StockAdjustmentPage.tsx",
  ]) {
    const source = fs.readFileSync(path.join(root, "src/modules/warehouse", file), "utf8");
    assert.match(source, /<FormDialog\b/, `${file} uses shared dialog`);
    assert.match(source, /<FormFooter\b/, `${file} uses shared footer`);
    assert.match(source, /useFormRecovery/, `${file} preserves unfinished input`);
    assert.match(source, /useUnsavedFormChanges/, `${file} protects unsaved edits`);
  }

  console.log("Inventory forms PASS: draft validation and shared create/edit form integration.");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
