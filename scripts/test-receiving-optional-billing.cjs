/* global require, __dirname, console, process */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const root = require("node:path").resolve(__dirname, "..");
const req = require("node:module").createRequire(root + "/package.json");

async function run() {
  const bundle = await req("esbuild").build({
    absWorkingDir: root,
    entryPoints: ["src/modules/purchasing/goods-receipts/billing.ts"],
    bundle: true,
    platform: "node",
    format: "cjs",
    write: false,
  });
  const module = { exports: {} };
  new Function("module", "exports", "require", bundle.outputFiles[0].text)(
    module, module.exports, req
  );
  const { emptyReceivingBilling, receivingBillingPayload, validateReceivingBilling } = module.exports;

  const empty = emptyReceivingBilling();
  assert.equal(validateReceivingBilling(empty, 105000), null);
  const payload = receivingBillingPayload(empty);
  assert.equal(Object.prototype.hasOwnProperty.call(payload, "supplier_invoice_date"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(payload, "supplier_invoice_due_date"), false);
  assert.equal(Object.prototype.hasOwnProperty.call(payload, "tax_invoice_date"), false);
  assert.equal(payload.shipping_fee_amount, 0);
  assert.equal(payload.admin_fee_amount, 0);
  assert.equal(payload.other_fee_amount, 0);
  assert.equal(payload.supplier_document_total, null);
  assert.equal(JSON.stringify(payload).includes('""'), true);

  const dated = receivingBillingPayload({
    ...empty,
    supplier_invoice_date: "2026-10-31",
    supplier_invoice_due_date: "2026-11-15",
    tax_invoice_date: "2026-10-31",
  });
  assert.equal(dated.supplier_invoice_date, "2026-10-31");
  assert.equal(dated.supplier_invoice_due_date, "2026-11-15");
  assert.equal(dated.tax_invoice_date, "2026-10-31");

  for (const name of [
    "DirectReceiveDialog.tsx",
    "ReceiveGoodsDialog.tsx",
    "EditReceivingDialog.tsx",
  ]) {
    const src = fs.readFileSync(
      root + "/src/modules/purchasing/goods-receipts/components/" + name, "utf8"
    );
    assert.match(src, /\.\.\.receivingBillingPayload\(billing\),/, name + " must omit empty dates");
    assert.doesNotMatch(src, /\.\.\.billing,/, name + " must not send unnormalized billing");
  }
  console.log("Receiving optional billing PASS: blank dates omitted from draft save, dated values preserved.");
}

run().catch(error => { console.error(error); process.exitCode = 1; });
