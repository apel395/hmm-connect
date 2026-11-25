/* global require, __dirname, console, process */
/* eslint @typescript-eslint/no-require-imports: "off" */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const read = (file) => fs.readFileSync(path.join(root, file), "utf8");
const has = (file, needle, message) =>
  assert.ok(read(file).includes(needle), `${message}: ${file} missing ${JSON.stringify(needle)}`);

async function run() {
  has("src/modules/pos/types.ts", "export type PosPage<T>", "shared pagination envelope is exported");
  has("src/modules/pos/types.ts", 'export type PosStatus = "DRAFT" | "POSTED" | "VOID"', "POS statuses are enumerated");
  has("src/modules/pos/types.ts", "export type PosSale", "serialized sale contract is exported");
  has("src/modules/pos/types.ts", "export type PosSalesPage", "sales page contract is exported");

  const api = read("src/modules/pos/api.ts");
  for (const call of [
    "api.get<PosOptions>(\"/pos/options\")",
    "api.get<PosSalesPage>(\"/pos\", { params })",
    "api.get<PosSale>(`/pos/${id}`)",
    "api.get<PosPage<PosProduct>>(\"/pos/products\", { params })",
    "api.post<PosSale>(\"/pos\", payload)",
  ]) {
    assert.ok(api.includes(call), `POS API is typed: ${call}`);
  }
  assert.ok(!api.includes("Record<string, unknown>"), "product params are not an untyped record");

  const operations = read("src/modules/pos/operationsApi.ts");
  for (const needle of ["export type OutletReport", "api.get<OutletReport>(\"/pos-operations/report\"", "api.put<OutletPolicy>"]) {
    assert.ok(operations.includes(needle), `operations API is typed: ${needle}`);
  }
  assert.ok(!operations.includes("api.get(\"/pos-operations/report\""), "report response is not untyped");

  const hooks = read("src/modules/pos/hooks/usePosData.ts");
  for (const needle of ["export function usePosSales", "export function usePosSaleDetail", "export function usePosOperations", "export function usePosOutletReport"]) {
    assert.ok(hooks.includes(needle), `typed POS hook is exported: ${needle}`);
  }
  assert.ok(!hooks.includes(": any"), "POS hooks contain no untyped values");

  const typeTest = read("src/modules/pos/contracts.type-test.ts");
  assert.ok((typeTest.match(/@ts-expect-error/g) ?? []).length >= 8, "type-level contract guards are asserted");

  for (const file of [
    "src/modules/pos/pages/PosOperationsPage.tsx",
    "src/modules/pos/pages/PosSalesPage.tsx",
    "src/modules/pos/pages/PosSettingsPage.tsx",
  ]) {
    assert.ok(read(file).includes("usePos") || read(file).includes("posApi"), `${file} consumes typed POS APIs`);
  }

  console.log("POS contracts PASS: typed responses, shared pagination, operations report and compile-time guards.");
}

run().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
