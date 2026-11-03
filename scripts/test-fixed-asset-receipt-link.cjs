/* global require, __dirname, console */
 /* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(
  path.join(root, "src/modules/finance/fixed-assets/FixedAssetDetailPage.tsx"),
  "utf8",
);
assert.match(source, /x\?\.goods_receipt_id/);
assert.match(source, /\/receiving\/\$\{x\.goods_receipt_id\}/);
assert.match(source, /Open Receiving Report/);
console.log("Fixed Asset receipt source link PASS.");
