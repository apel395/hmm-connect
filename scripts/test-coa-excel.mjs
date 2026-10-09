import assert from "node:assert/strict";
import console from "node:console";
import { createRequire } from "node:module";
import { build } from "esbuild";
const require = createRequire(import.meta.url);
const XLSX = require("xlsx");
const compiled = await build({
  entryPoints: ["src/modules/master/chart-of-accounts/excel.ts"], bundle: true, write: false,
  platform: "node", format: "cjs", external: ["xlsx"],
  plugins: [{ name: "accounts-api", setup(build) {
    build.onResolve({ filter: /^\.\/api$/ }, () => ({ path: "api", namespace: "mock" }));
    build.onLoad({ filter: /.*/, namespace: "mock" }, () => ({ contents: "export const getAccounts = params => globalThis.fetchAccounts(params);", loader: "js" }));
  } }],
});
const mod = { exports: {} };
new Function("module", "exports", "require", compiled.outputFiles[0].text)(mod, mod.exports, require);
const calls = [];
const record = id => ({ id, account_code: id === 1 ? "001-001" : `100-300-${id}`, account_name: `Account ${id}`, account_type: "ASSET", account_subtype: "OTHER", parent_account_id: null, normal_balance: "DEBIT", is_posting: true, is_active: false, is_system: false, description: "" });
globalThis.fetchAccounts = async params => {
  calls.push(params);
  return { total_pages: 3, items: Array.from({ length: params.page === 3 ? 34 : 100 }, (_, i) => record((params.page - 1) * 100 + i + 1)) };
};
const filters = { search: "Account", account_type: "ASSET", is_active: false, is_posting: true, sort_by: "account_code", sort_order: "desc" };
const accounts = await mod.exports.loadExportAccounts(filters);
assert.equal(accounts.length, 234);
assert.equal(calls.length, 3);
for (const call of calls) for (const [key, value] of Object.entries(filters)) assert.equal(call[key], value);
const workbook = mod.exports.accountWorkbook(accounts);
const bytes = XLSX.write(workbook, { type: "buffer", bookType: "xlsx" });
assert.equal(bytes.subarray(0, 2).toString(), "PK");
const reopened = XLSX.read(bytes, { type: "buffer" });
const sheet = reopened.Sheets["Chart of Accounts"];
assert.equal(sheet.A2.t, "s");
assert.equal(sheet.A2.v, "001-001");
const rows = XLSX.utils.sheet_to_json(sheet);
assert.equal(rows.length, 234);
assert.equal(rows[0].Status, "Archived");
assert.equal(rows[0]["Posting Account"], "Yes");
assert.equal(rows[233]["Account Name"], "Account 234");
const empty = mod.exports.accountWorkbook([]);
assert.equal(XLSX.utils.sheet_to_json(empty.Sheets["Chart of Accounts"]).length, 0);
console.log("COA Excel export checks passed: pagination, filters, XLSX and text codes");
