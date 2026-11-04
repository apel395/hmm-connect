/* global require, __dirname, global, window, console, process, EventTarget, Event */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const requireProject = require("node:module").createRequire(path.join(root, "package.json"));
const { build } = requireProject("esbuild");
const React = requireProject("react");
const renderer = requireProject("react-test-renderer");
global.IS_REACT_ACT_ENVIRONMENT = true;

async function bundledModule(entry) {
  const result = await build({
    absWorkingDir: root,
    tsconfig: path.join(root, "tsconfig.app.json"),
    entryPoints: [entry],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    external: ["react"],
  });
  const module = { exports: {} };
  new Function("module", "exports", "require", result.outputFiles[0].text)(
    module,
    module.exports,
    (name) => (name === "react" ? React : requireProject(name)),
  );
  return module.exports;
}

async function run() {
  const { initialPurchaseOrderDraft, validPurchaseOrderDraft } = await bundledModule(
    "src/modules/purchasing/purchase-order/components/purchaseOrderDraft.ts",
  );

  const blank = initialPurchaseOrderDraft();
  assert.equal(blank.creationType, "FROM_PR");
  assert.equal(blank.items.length, 0);
  assert.ok(validPurchaseOrderDraft(blank));

  const fromPR = initialPurchaseOrderDraft({
    creation_type: "FROM_PR",
    supplier_id: 5,
    source_pr_id: 73,
    source_pr_number: "PR-73",
    business_unit_id: 2,
    order_date: "2026-11-04",
    expected_date: "2026-11-05",
    items: [{ product_id: 77, product_name: "Blender", product_code: "IT-77", quantity: 2, unit_price: 125000, uom: "PCS" }],
  });
  assert.equal(fromPR.selectedPRs[0].id, 73);
  assert.equal(fromPR.items[0].quantity, 2);
  assert.equal(fromPR.items[0].unit_price, 125000);
  assert.equal(fromPR.items[0].source_pr_number, "PR-73");
  assert.ok(validPurchaseOrderDraft(fromPR));
  assert.equal(validPurchaseOrderDraft({ ...fromPR, items: [{ quantity: "2", unit_price: 125000 }] }), false);
  assert.equal(validPurchaseOrderDraft({ ...fromPR, items: [{ quantity: 2, unit_price: Infinity }] }), false);

  const editing = initialPurchaseOrderDraft({
    creation_type: "DIRECT", supplier_id: 6, notes: "Keep previous notes", items: [{ product_id: 12, quantity: 3, unit_price: 2000 }],
  });
  assert.equal(editing.creationType, "DIRECT");
  assert.equal(editing.notes, "Keep previous notes");
  assert.equal(editing.items[0].quantity * editing.items[0].unit_price, 6000);

  const useUnsavedFormChanges = (await bundledModule("src/hooks/useUnsavedFormChanges.ts")).default;
  let allow = false;
  let prompts = 0;
  let closes = 0;
  global.window = Object.assign(new EventTarget(), {
    confirm: () => { prompts += 1; return allow; },
  });
  let closeForm;
  function TestForm({ dirty = false, busy = false, recoverable = true }) {
    closeForm = useUnsavedFormChanges({ dirty, busy, recoverable, onClose: () => { closes += 1; } });
    return null;
  }
  let view;
  await renderer.act(async () => { view = renderer.create(React.createElement(TestForm)); });
  await renderer.act(async () => closeForm());
  assert.equal(closes, 1, "clean form closes without confirmation");
  await renderer.act(async () => view.update(React.createElement(TestForm, { dirty: true })));
  const unload = new Event("beforeunload", { cancelable: true });
  window.dispatchEvent(unload);
  assert.equal(unload.defaultPrevented, true, "dirty form warns before leaving the page");
  await renderer.act(async () => closeForm());
  assert.equal(closes, 1, "declined confirmation keeps form open");
  assert.equal(prompts, 1);
  allow = true;
  await renderer.act(async () => closeForm());
  assert.equal(closes, 2, "accepted confirmation closes form");
  await renderer.act(async () => view.update(React.createElement(TestForm, { dirty: true, busy: true })));
  await renderer.act(async () => closeForm());
  assert.equal(closes, 2, "pending save prevents closing");
  await renderer.act(async () => view.unmount());

  console.log("Purchase Order forms PASS: initialization, draft shape, edit values, unsaved confirmation, and pending-save guard.");
}

run().catch((error) => { console.error(error); process.exitCode = 1; });
