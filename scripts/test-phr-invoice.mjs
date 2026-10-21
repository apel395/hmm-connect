import process from "node:process";
import console from "node:console";
import assert from "node:assert/strict";
import { build } from "esbuild";
import { createRequire } from "node:module";
import { writeFileSync } from "node:fs";
const require = createRequire(import.meta.url);
const { createElement } = require("react");
const { renderToStaticMarkup } = require("react-dom/server");
const compiled = await build({
  entryPoints: ["src/modules/finance/accounts-receivable/PHRInvoice.tsx"],
  bundle: true,
  write: false,
  platform: "node",
  format: "cjs",
  tsconfig: "tsconfig.app.json",
  external: ["react", "react/jsx-runtime"],
});
const mod = { exports: {} };
new Function("module", "exports", "require", compiled.outputFiles[0].text)(
  mod,
  mod.exports,
  require,
);
const sample = {
  invoice_number: "MMH-PHR/TEST/2026",
  invoice_date: "2026-10-01",
  amount: "330.00",
  received_amount: "0",
  outstanding_amount: "330.00",
  customer_name: "PT. Pertamina Hulu Rokan",
  print_ready: true,
  layout: {
    title: "INVOICE",
    company_address: "Jln. Yos Sudarso 12 A, Pekanbaru - Riau - Indonesia",
    billing_address:
      "16th Floor, RDTX Place Building\nJl. Prof. Dr. Satrio Kav. E-IV Kuningan\nJakarta Selatan 12930",
    attention: "Finance & Accounting Dept.",
    contract_number: "CONTRACT-TEST",
    contract_date: "2025-08-01",
    payment_instructions:
      "Payment can be transferred to our bank in\nBANK MANDIRI\nIDR Account A/C: 0000000000\na/n: MUTIARA MERDEKA HOTEL",
    signer_name: "Authorized Signatory",
    signer_position: "Project Manager",
  },
  document: {
    description:
      "Invoice Catering Service in Minas for periode 01–30 Juni 2026",
    lines: [
      {
        registration_number: "REG-001",
        description:
          "Biweekly Catering Service Minas for Periode 01–15 Juni 2026",
        amount: "100.00",
      },
      {
        registration_number: "REG-002",
        description:
          "Biweekly Catering Service Minas for Periode 16–30 Juni 2026",
        amount: "200.00",
      },
    ],
    tax_label: "Tax 10% PB1 Jasa Catering",
    tax_amount: "30.00",
    amount_in_words:
      "Tiga Ratus Tiga Puluh Rupiah",
  },
};
const render = (data) =>
  renderToStaticMarkup(createElement(mod.exports.default, { data }));
const html = render(sample);
assert.ok(html.includes("Reg No."));
assert.ok(html.includes("330,00"));
assert.ok(html.includes("300,00"));
assert.ok(html.includes('data-print-ready="true"'));
assert.ok(!html.includes("Complete invoice"));
assert.ok(
  render({ ...sample, print_ready: false }).includes(
    'data-print-ready="false"',
  ),
);
assert.ok(!html.includes("Received"));
assert.ok(
  render({
    ...sample,
    layout: { ...sample.layout, show_settlement: true },
  }).includes("Outstanding"),
);
assert.ok(
  render({
    ...sample,
    document: { ...sample.document, description: "<script>alert(1)</script>" },
  }).includes("&lt;script&gt;"),
);
// Amounts from the accepted catering invoice; no historical values are defaults.
const accepted = {
  ...sample, invoice_number: "MMH-MNS/186/VI/2026", amount: "516179829.00", outstanding_amount: "516179829.00",
  document: {...sample.document, lines: [
    {...sample.document.lines[0], registration_number: "268/MMH-MINAS/VI/2026", amount: "230817730.00"},
    {...sample.document.lines[1], registration_number: "274/MMH-MINAS/VI/2026", amount: "238436660.00"},
  ], tax_amount: "46925439.00", amount_in_words: "Lima Ratus Enam Belas Juta Seratus Tujuh Puluh Sembilan Ribu Delapan Ratus Dua Puluh Sembilan Rupiah"},
};
const acceptedHtml = render(accepted);
for (const value of ["469.254.390,00", "46.925.439,00", "516.179.829,00", "268/MMH-MINAS/VI/2026", "274/MMH-MINAS/VI/2026", "Authorized by,", 'src="/logoprint.jpeg"']) assert.ok(acceptedHtml.includes(value), value);
assert.ok(!acceptedHtml.includes("meterai") && !acceptedHtml.includes("data:image"));
if (process.argv.includes("--preview")) {
  writeFileSync(
    "/tmp/phr-preview.html",
    '<!doctype html><html><head><meta charset="utf-8"><style>*{box-sizing:border-box}body{margin:0}</style></head><body>' +
      acceptedHtml +
      "</body></html>",
  );
  writeFileSync(
    "/tmp/phr-long-preview.html",
    '<!doctype html><html><head><meta charset="utf-8"><style>*{box-sizing:border-box}body{margin:0}</style></head><body>' +
      render({
        ...sample,
        document: {
          ...sample.document,
          lines: Array.from({ length: 40 }, (_, i) => ({
            ...sample.document.lines[0],
            registration_number: `REG-${i + 1}`,
            description:
              "Catering service with a long description for the service period, location and work order reference.",
          })),
        },
      }) +
      "</body></html>",
  );
}
console.log("PHR print rendering checks passed");
