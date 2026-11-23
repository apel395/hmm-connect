import assert from "node:assert/strict";
import { build } from "esbuild";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const compiled = await build({
  stdin: {
    contents: `export {parseInvoiceErrorDetail, parseInvoiceError, invoiceErrorMessage} from "./src/modules/finance/supplier-invoices/errors";`,
    resolveDir: process.cwd(),
    loader: "ts",
  },
  bundle: true,
  write: false,
  platform: "node",
  format: "cjs",
  tsconfig: "tsconfig.app.json",
});
const mod = { exports: {} };
new Function("module", "exports", "require", compiled.outputFiles[0].text)(mod, mod.exports, require);
const { parseInvoiceErrorDetail, parseInvoiceError, invoiceErrorMessage } = mod.exports;

const stringError = parseInvoiceErrorDetail("Invoice charges and taxes do not match the supplier document total");
assert.equal(stringError.message, "Invoice charges and taxes do not match the supplier document total");
assert.equal(stringError.fields.length, 0);

const pydanticError = parseInvoiceErrorDetail([
  { loc: ["body", "lines", 2, "tax_rate"], msg: "Input should be less than or equal to 100" },
]);
assert.equal(pydanticError.fields[0].path, "lines[2].tax_rate");
assert.match(pydanticError.fields[0].message, /less than or equal/);

const structured = parseInvoiceError({
  response: {
    data: {
      detail: {
        message: "Invoice charges and taxes do not match the supplier document total",
        code: "SUPPLIER_DOCUMENT_TOTAL_MISMATCH",
        fields: [{
          path: "supplier_document_total",
          message: "Document Total must equal the recalculated Invoice Total (4,111.08).",
          actual: "4111.00",
          expected: "4111.08",
        }],
        totals: { calculated_total: "4111.08" },
      },
    },
  },
});
assert.equal(structured.code, "SUPPLIER_DOCUMENT_TOTAL_MISMATCH");
assert.equal(structured.fields[0].path, "supplier_document_total");
assert.equal(structured.fields[0].expected, "4111.08");
assert.equal(structured.totals.calculated_total, "4111.08");
assert.match(invoiceErrorMessage({ response: { data: { detail: structured } } }), /update Document Total/);

console.log("Supplier invoice errors PASS: string, Pydantic and structured field metadata parsed.");
