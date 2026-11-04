/* global require, __dirname, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const requireProject = require("node:module").createRequire(path.join(root, "package.json"));
const { build } = requireProject("esbuild");

async function load(entry) {
  const output = await build({
    absWorkingDir: root,
    tsconfig: path.join(root, "tsconfig.app.json"),
    entryPoints: [entry],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
  });
  const module = { exports: {} };
  new Function("module", "exports", "require", output.outputFiles[0].text)(module, module.exports, requireProject);
  return module.exports;
}

async function run() {
  const pr = await load("src/modules/purchasing/requisition/components/purchaseRequisitionDraft.ts");
  const ml = await load("src/modules/purchasing/market-list/marketListDraft.ts");
  const defaults = {
    business_unit_id: 1,
    department_id: 4,
    location_id: 8,
  };
  const newPR = pr.initialPurchaseRequisitionDraft(undefined, defaults);
  assert.equal(newPR.businessUnitId, 1);
  assert.equal(newPR.departmentId, 4);
  assert.equal(newPR.locationId, 8);
  assert.equal(newPR.items.length, 1);
  assert.ok(pr.validPurchaseRequisitionDraft(newPR));

  const editedPR = pr.initialPurchaseRequisitionDraft({
    id: 15,
    business_unit_id: 2,
    department_id: 5,
    location_id: 9,
    request_date: "2026-11-04",
    notes: "Existing request",
    items: [{product_id: 77, product_code: "IT-77", product_name: "Blender", quantity: 3, estimated_price: 150000}],
  });
  assert.equal(editedPR.businessUnitId, 2);
  assert.equal(editedPR.items[0].quantity, 3);
  assert.equal(editedPR.items[0].estimated_price, 150000);
  assert.equal(editedPR.products[0].name, "Blender");
  assert.ok(pr.validPurchaseRequisitionDraft(editedPR));
  assert.equal(pr.validPurchaseRequisitionDraft({...editedPR,items:[{product_id:77,quantity:-1,estimated_price:NaN}]}),false);

  const newML = ml.initialMarketListDraft();
  assert.equal(newML.rows.length, 1);
  assert.ok(ml.validMarketListDraft(newML));
  const editedML = ml.initialMarketListDraft({
    id: 27,
    business_unit_id: 3,
    department_id: 6,
    location_id: 11,
    request_date: "2026-11-04",
    expiry_date: "2026-11-09",
    notes: "Fruit order",
    items: [{product_id: 52, product_name: "Apple", quantity: 4, estimated_price: 40000, is_taxable: true, tax_rate: 11}],
  });
  assert.equal(editedML.bu, 3);
  assert.equal(editedML.rows[0].estimated_price, 40000);
  assert.equal(editedML.products[0].is_taxable, true);
  assert.equal(editedML.products[0].tax_rate, 11);
  assert.equal(editedML.expiry, "2026-11-09");
  assert.ok(ml.validMarketListDraft(editedML));
  assert.equal(ml.validMarketListDraft({...editedML,rows:[{product_id:52,quantity:"4",estimated_price:40000}]}),false);

  console.log("Purchasing forms PASS: PR defaults/edit values, Market List totals inputs/tax metadata, and recovery schemas.");
}

run().catch(error => { console.error(error); process.exitCode = 1; });
