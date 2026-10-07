import console from "node:console";
import assert from "node:assert/strict";
import { build } from "esbuild";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
async function compile(entry) {
  const result = await build({
    entryPoints: [entry],
    bundle: true,
    write: false,
    platform: "node",
    format: "cjs",
    tsconfig: "tsconfig.app.json",
    plugins: [
      {
        name: "api-test",
        setup(b) {
          b.onResolve({ filter: /^@\/api\/client$/ }, () => ({
            path: "api",
            namespace: "mock",
          }));
          b.onLoad({ filter: /.*/, namespace: "mock" }, () => ({
            contents:
              "export default { get: (...args) => globalThis.inventoryTestApi(...args) };",
            loader: "js",
          }));
        },
      },
    ],
  });
  const mod = { exports: {} };
  new Function("module", "exports", "require", result.outputFiles[0].text)(
    mod,
    mod.exports,
    require,
  );
  return mod.exports;
}
const { collectReportPages, renderInventoryPrint } = await compile(
  "src/utils/inventoryPrint.ts",
);
const calls = [];
const rows = Array.from({ length: 205 }, (_, i) => ({ id: i + 1 }));
const complete = await collectReportPages(async (page) => {
  calls.push(page);
  return {
    items: rows.slice((page - 1) * 100, page * 100),
    total_items: 205,
    total_pages: 3,
  };
});
assert.equal(complete.items.length, 205);
assert.deepEqual(calls, [1, 2, 3]);
await assert.rejects(
  () =>
    collectReportPages(async () => ({
      items: [{ id: 1 }],
      total_items: 2,
      total_pages: 2,
    })),
  /complete report/,
);
await assert.rejects(
  () =>
    collectReportPages(async (page) => ({
      items: [{ id: page }],
      total_items: page === 1 ? 2 : 3,
      total_pages: 2,
    })),
  /Data changed/,
);
await assert.rejects(
  () =>
    collectReportPages(async () => ({
      items: [],
      total_items: 1,
      total_pages: 1,
    })),
  /complete report/,
);
assert.equal(
  (
    await collectReportPages(async () => ({
      items: [],
      total_items: 0,
      total_pages: 0,
    }))
  ).items.length,
  0,
);
const builders = await compile(
  "src/modules/warehouse/inventory/print/reports.ts",
);
const stock = [
  {
    id: 1,
    product_id: 10,
    product_code: "1-100001",
    product_name: "Vegetables <script>bad()</script>",
    warehouse_id: 1,
    warehouse_name: "Rumbai",
    uom: "KG",
    quantity: 5,
    average_cost: 100,
    stock_value: 500,
    inventory_account_code: "100-300-100",
    inventory_account_name: "Food",
  },
  {
    id: 2,
    product_id: 11,
    product_code: "2-100001",
    product_name: "Water",
    warehouse_id: 1,
    warehouse_name: "Rumbai",
    uom: "BOX",
    quantity: 2,
    average_cost: 200,
    stock_value: 400,
    inventory_account_code: "100-300-500",
    inventory_account_name: "Beverage",
  },
];
const moves = [
  {
    id: 1,
    product_id: 10,
    product_code: "1-100001",
    product_name: "Vegetables",
    warehouse_id: 1,
    warehouse_name: "Rumbai",
    movement_type: "IN",
    movement_date: "2026-01-02",
    quantity: 5,
    in_quantity: 5,
    out_quantity: 0,
    unit_cost: 100,
    movement_value: 500,
    inventory_account_code: "100-300-100",
  },
  {
    id: 2,
    product_id: 10,
    product_code: "1-100001",
    product_name: "Vegetables",
    warehouse_id: 1,
    warehouse_name: "Rumbai",
    movement_type: "OUT",
    movement_date: "2026-01-03",
    quantity: 2,
    in_quantity: 0,
    out_quantity: 2,
    unit_cost: 100,
    movement_value: 200,
    inventory_account_code: "100-300-100",
  },
];
const requests = [];
globalThis.inventoryTestApi = async (path, { params } = {}) => {
  requests.push({ path, params });
  let items = path === "/inventory" ? stock : moves;
  if (params?.product_id)
    items = items
      .filter((r) => r.product_id === params.product_id)
      .map((r, i) => ({ ...r, running_quantity: i === 0 ? 15 : 13 }));
  return {
    data: {
      items,
      total_items: items.length,
      total_pages: 1,
      history_balances: [
        { warehouse_id: 1, opening_quantity: 10, closing_quantity: 13 },
      ],
    },
  };
};
const valuation = await builders.stockListReport(
  { as_of: "2026-01-31" },
  "As of January",
);
assert.equal(valuation.groups.length, 2);
assert.equal(valuation.footer[6], "Rp 900,00");
assert.equal(valuation.footer[4], null, "Do not sum KG and BOX quantities");
const movement = await builders.movementReport(
  { date_from: "2026-01-01" },
  "January",
);
assert.equal(movement.footer[8], "Rp 300,00");
assert.equal(movement.groups[0].rows[1][5], "OUT");
const card = await builders.stockCardReport(
  { account_id: 1, date_from: "2026-01-01", date_to: "2026-01-31" },
  "January",
);
assert.match(card.groups[0].detail, /Opening quantity: 10/);
assert.equal(card.groups[0].rows[1][4], "13");
assert.equal(card.groups[0].rows[1][5], "Rp -200,00");
assert.ok(
  requests.some(
    (r) => r.params?.product_id === 10 && r.params.account_id === 1,
  ),
);
assert.ok(
  card.groups.some((g) => g.title.includes("Water") && g.rows.length === 0),
);
assert.equal(card.footer[5], "Rp 300,00");
const html = renderInventoryPrint(
  valuation,
  "Finance <Admin>",
  new Date("2026-01-01T00:00:00Z"),
);
assert.ok(html.includes("&lt;script&gt;"));
assert.ok(!html.includes("<script>"));
assert.ok(html.includes("Finance &lt;Admin&gt;"));
assert.ok(html.includes("counter(page)"));
assert.ok(html.includes("counter(pages)"));
assert.ok(html.includes("table-header-group"));
assert.ok(html.includes("Records: 2"));
assert.ok(html.includes("WIB"));
console.log(
  "Inventory print passed: all pages, changing/incomplete data rejected, grouped valuation, mixed-unit safety, signed movements, true running balances, escaped fields and print metadata.",
);
