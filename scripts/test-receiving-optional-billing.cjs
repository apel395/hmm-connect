/* global require, __dirname, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
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
  assert.equal(empty.discount_account_id, null);
  assert.equal(payload.discount_account_id, null);
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
  const billingFields = fs.readFileSync(
    root + "/src/modules/purchasing/goods-receipts/components/ReceivingBillingFields.tsx", "utf8"
  );
  assert.match(billingFields, /label="Discount account"/, "receiving billing exposes a discount account selector");
  assert.match(billingFields, /dataField="discount_account_id"/, "discount account uses a stable validation path");
  assert.match(billingFields, /discount_account_id\?\?undefined/, "discount selector binds the billing account id");
  assert.match(billingFields, /\["INCOME","EXPENSE"\]/, "discount account is limited to credit-normal income/expense accounts");
  assert.match(billingFields, /==="CREDIT"/, "discount account stays credit-normal");
  console.log("Receiving optional billing PASS: blank dates omitted from draft save, dated values preserved, discount COA selectable.");
}

run().catch(error => { console.error(error); process.exitCode = 1; });
