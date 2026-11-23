import assert from "node:assert/strict";
import { build } from "esbuild";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const compiled = await build({
  stdin: {
    contents: `export {computeInvoiceTotals, buildInvoicePayload, withSyncedDocumentTotal, roundMoney} from "./src/modules/finance/supplier-invoices/totals";`,
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
const { computeInvoiceTotals, buildInvoicePayload, withSyncedDocumentTotal, roundMoney } = mod.exports;

const line = (extra = {}) => ({
  id: 9,
  product_id: 3,
  description: "Item",
  quantity: 1,
  unit_price: 100,
  is_taxable: true,
  tax_rate: 11,
  tax_amount: 11,
  line_amount: 111,
  line_total: 111,
  fixed_asset: { id: 4 },
  ...extra,
});

const totals = computeInvoiceTotals([line()], { shipping_fee_amount: 5 });
assert.equal(roundMoney(totals.subtotal), 100, "subtotal");
assert.equal(roundMoney(totals.tax), 11, "PPN");
assert.equal(roundMoney(totals.total), 116, "total includes fees");

const form = {
  id: 7,
  status: "DRAFT",
  internal_invoice_number: "INV-1",
  supplier_id: 2,
  supplier_invoice_number: "SUP-1",
  supplier_document_total: 116,
  subtotal: 100,
  total_amount: 116,
  balance_amount: 116,
  vat_decision: "DOCUMENT_PPN",
  invoice_date: "2026-11-01",
  due_date: "2026-12-01",
  currency: "IDR",
  discount_amount: 0,
  withholding_tax_amount: 0,
  shipping_fee_amount: 5,
  admin_fee_amount: 0,
  other_fee_amount: 0,
  source_type: "LIVE",
  notes: "",
  lines: [line()],
};
const payload = buildInvoicePayload(form, totals);
for (const stale of ["id", "status", "internal_invoice_number", "subtotal", "total_amount", "balance_amount", "vat_decision"]) {
  assert.equal(Object.hasOwn(payload, stale), false, `payload must not echo ${stale}`);
}
assert.equal(payload.tax_amount, 11, "header tax is derived from lines");
assert.equal(payload.supplier_document_total, 116, "document total kept");
assert.equal(Object.hasOwn(payload.lines[0], "tax_amount"), false, "line tax is derived by backend");
assert.equal(Object.hasOwn(payload.lines[0], "id"), false, "line id is not submitted");
assert.equal(Object.hasOwn(payload.lines[0], "fixed_asset"), false, "display-only line state is not submitted");
assert.equal(payload.lines[0].description, "Item");

const correctedLines = [line({ is_taxable: false, tax_rate: 0 })];
const synced = withSyncedDocumentTotal(form, correctedLines, totals.total);
assert.equal(synced.supplier_document_total, 105, "document total follows PPN correction");
assert.equal(synced.lines[0].is_taxable, false);

const manual = withSyncedDocumentTotal({ ...form, supplier_document_total: 120 }, correctedLines, totals.total);
assert.equal(manual.supplier_document_total, 120, "manually corrected document total is preserved");

const withDecision = withSyncedDocumentTotal(form, correctedLines, totals.total, { vat_decision: "NO_PPN_RECORDED", tax_invoice_number: "" });
assert.equal(withDecision.vat_decision, "NO_PPN_RECORDED");
assert.equal(withDecision.supplier_document_total, 105);

const withFee = withSyncedDocumentTotal(form, form.lines, totals.total, { shipping_fee_amount: 8 });
assert.equal(withFee.supplier_document_total, 119, "document total follows fee correction");
assert.equal(withFee.shipping_fee_amount, 8);

console.log("Supplier invoice totals PASS: explicit payload, PPN/fee document-total sync, manual override preserved.");
