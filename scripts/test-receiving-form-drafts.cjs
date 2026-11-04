/* global require, __dirname, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const req = require("node:module").createRequire(path.join(root, "package.json"));

async function load(entry) {
  const result = await req("esbuild").build({
    absWorkingDir: root,
    tsconfig: path.join(root, "tsconfig.app.json"),
    entryPoints: [entry],
    bundle: true,
    write: false,
    format: "cjs",
    platform: "node",
  });
  const module = { exports: {} };
  new Function("module", "exports", "require", result.outputFiles[0].text)(module, module.exports, req);
  return module.exports;
}

async function run() {
  const { emptyReceivingBilling } = await load("src/modules/purchasing/goods-receipts/billing.ts");
  const { validReceivingLinesDraft, validReceivingProductLinesDraft, validReceivingEditDraft, restoredReceivingQuantity } =
    await load("src/modules/purchasing/goods-receipts/receivingFormDrafts.ts");

  const billing = emptyReceivingBilling();
  const line = { product_id: 17, quantity: 3, unit_cost: 125000 };
  const base = { billing, receivedAt: "2026-11-04T09:00", notes: "" };
  assert.equal(validReceivingLinesDraft({ ...base, lines: [line] }), true);
  assert.equal(validReceivingProductLinesDraft({ ...base, lines: [line], productRows: [] }), true);
  assert.equal(validReceivingProductLinesDraft({ ...base, lines: [line] }), false);
  assert.equal(validReceivingEditDraft({ ...base, items: [{ ...line, row_key: "existing-20" }], productRows: [] }), true);
  assert.equal(validReceivingLinesDraft({ ...base, lines: [{ ...line, quantity: "3" }] }), false);
  assert.equal(validReceivingEditDraft({ ...base, items: [line], billing: {} }), false);
  assert.equal(validReceivingLinesDraft({ ...base, lines: null }), false);
  assert.equal(restoredReceivingQuantity(4, 6), 4, "restored quantity never exceeds the current remaining quantity");
  assert.equal(restoredReceivingQuantity(4, -2), 0, "restored quantity cannot be negative");
  assert.equal(restoredReceivingQuantity(0, 6), 0, "fully received PO lines cannot recover old quantities");

  console.log("Receiving form drafts PASS: stored line schemas, edit line schema, and quantity reconciliation.");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
