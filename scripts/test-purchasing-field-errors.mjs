import assert from "node:assert/strict";
import { build } from "esbuild";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const compiled = await build({
  stdin: {
    contents: `export {mapPurchasingFieldPaths, readPurchasingError} from "./src/modules/purchasing/fieldErrors";`,
    resolveDir: process.cwd(),
    loader: "ts",
  },
  bundle: true,
  write: false,
  platform: "node",
  format: "cjs",
  tsconfig: "tsconfig.app.json",
  external: ["react"],
});
const mod = { exports: {} };
new Function("module", "exports", "require", compiled.outputFiles[0].text)(mod, mod.exports, require);
const { mapPurchasingFieldPaths, readPurchasingError } = mod.exports;

const legacy = readPurchasingError({
  response: { data: { detail: "Market List item exceeds remaining quantity" } },
});
assert.equal(legacy.message, "Market List item exceeds remaining quantity");
assert.deepEqual(legacy.fields, {});

const structured = readPurchasingError({
  response: {
    data: {
      detail: {
        message: "Receiving could not be saved",
        code: "RECEIVING_QUANTITY_EXCEEDED",
        fields: [{
          path: "items[2].quantity",
          message: "Quantity exceeds remaining quantity.",
          actual: "10",
          expected: "5",
        }],
      },
    },
  },
});
assert.equal(structured.message, "Receiving could not be saved");
assert.equal(structured.fields["items[2].quantity"], "Quantity exceeds remaining quantity.");

const dotted = readPurchasingError({
  response: {
    data: {
      detail: {
        fields: [{ path: "items.0.unit_cost", message: "Unit cost must be positive." }],
      },
    },
  },
});
assert.equal(dotted.fields["items[0].unit_cost"], "Unit cost must be positive.");

const pydantic = readPurchasingError({
  response: {
    data: {
      detail: [{
        loc: ["body", "items", 1, "unit_cost"],
        msg: "Input should be greater than 0",
      }],
    },
  },
});
assert.equal(pydantic.fields["items[1].unit_cost"], "Input should be greater than 0");

const remapped = mapPurchasingFieldPaths(
  { message: "Receiving rejected", fields: { "items[0].quantity": "Exceeds remaining" } },
  (path) => path.replace(/^items\[(\d+)\]/, (_, index) => `items[${[2, 5][Number(index)] ?? Number(index)}]`),
);
assert.equal(remapped.fields["items[2].quantity"], "Exceeds remaining");
assert.equal(remapped.message, "Receiving rejected");

console.log("Purchasing field errors PASS: legacy, structured, dotted, Pydantic and row-mapped paths parsed.");
