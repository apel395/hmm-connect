import api from "@/api/client";
import {
  collectReportPages,
  printMoney as money,
  printNumber as num,
  type InventoryPrintReport,
  type PrintColumn,
  type PrintGroup,
  type ReportPage,
} from "@/utils/inventoryPrint";

type Row = Record<string, any> & { id: number };
type Params = Record<string, unknown>;
const stockColumns: PrintColumn[] = [
  { label: "Item code", code: true },
  { label: "Item name" },
  { label: "Warehouse" },
  { label: "Unit" },
  { label: "Quantity", numeric: true },
  { label: "Average cost", numeric: true },
  { label: "Stock value", numeric: true },
];
const accountName = (row: Row) =>
  row.inventory_account_code
    ? `${row.inventory_account_code} — ${row.inventory_account_name}`
    : "Unmapped inventory account";
const total = (rows: Row[], key: string) =>
  rows.reduce((sum, row) => sum + Number(row[key] ?? 0), 0);
const grouped = (rows: Row[], key: (row: Row) => string) => {
  const groups = new Map<string, Row[]>();
  for (const row of rows) {
    const name = key(row);
    if (!groups.has(name)) groups.set(name, []);
    groups.get(name)!.push(row);
  }
  return [...groups].sort(([a], [b]) => a.localeCompare(b));
};
export async function allInventoryRows(path: string, params: Params = {}) {
  return collectReportPages<Row>(
    async (page) =>
      (
        await api.get<ReportPage<Row>>(path, {
          params: { ...params, page, page_size: 100 },
        })
      ).data,
  );
}

export async function stockListReport(
  params: Params,
  context: string,
  title = "Stock List",
): Promise<InventoryPrintReport> {
  const data = await allInventoryRows("/inventory", params);
  const groups = grouped(data.items, accountName).map(([, items]) => ({
    title: items[0].inventory_account_name || "Unmapped inventory account",
    rows: items
      .sort(
        (a, b) =>
          String(a.product_code).localeCompare(String(b.product_code)) ||
          String(a.warehouse_name).localeCompare(String(b.warehouse_name)),
      )
      .map((row) => [
        row.product_code,
        row.product_name,
        row.warehouse_name,
        row.uom,
        num(row.quantity),
        money(row.average_cost),
        money(row.stock_value),
      ]),
    footer: [
      "Subtotal",
      null,
      null,
      null,
      null,
      null,
      money(total(items, "stock_value")),
    ],
  }));
  return {
    title,
    context,
    columns: stockColumns,
    groups,
    rowCount: data.items.length,
    footer: [
      "Grand total",
      null,
      null,
      null,
      null,
      null,
      money(total(data.items, "stock_value")),
    ],
  };
}

export async function warehouseValuationReport(
  params: Params,
  context: string,
): Promise<InventoryPrintReport> {
  const data = await allInventoryRows("/inventory", params);
  const items = grouped(data.items, (row) => String(row.warehouse_id));
  return {
    title: "Stock Valuation by Warehouse",
    context,
    rowCount: data.items.length,
    columns: [
      { label: "Warehouse" },
      { label: "Stock lines", numeric: true },
      { label: "Low-stock lines", numeric: true },
      { label: "Stock value", numeric: true },
    ],
    groups: [
      {
        title: "Warehouses",
        rows: items.map(([, rows]) => [
          `${rows[0].warehouse_code || ""} ${rows[0].warehouse_name}`.trim(),
          num(rows.length),
          num(rows.filter((r) => r.low_stock).length),
          money(total(rows, "stock_value")),
        ]),
      },
    ],
    footer: [
      "Grand total",
      num(data.items.length),
      num(data.items.filter((r) => r.low_stock).length),
      money(total(data.items, "stock_value")),
    ],
  };
}

export async function lowStockReport(
  params: Params,
  context: string,
): Promise<InventoryPrintReport> {
  const data = await allInventoryRows("/inventory", {
    ...params,
    health: "LOW_STOCK",
  });
  return {
    title: "Low Stock",
    context,
    rowCount: data.items.length,
    columns: [
      { label: "Item code", code: true },
      { label: "Item name" },
      { label: "Warehouse" },
      { label: "Unit" },
      { label: "On hand", numeric: true },
      { label: "Minimum", numeric: true },
      { label: "Shortage", numeric: true },
    ],
    groups: grouped(data.items, accountName).map(([, items]) => ({
      title: items[0].inventory_account_name || "Unmapped inventory account",
      rows: items.map((r) => [
        r.product_code,
        r.product_name,
        r.warehouse_name,
        r.uom,
        num(r.quantity),
        num(r.minimum_stock),
        num(r.shortage),
      ]),
    })),
  };
}

const reference = (row: Row) =>
  row.receipt_number ||
  row.purchase_order_number ||
  (row.reference_number !== "-" && row.reference_number) ||
  row.movement_number;
const direction = (row: Row) => (row.movement_type === "OUT" ? "OUT" : "IN");
const chronological = (a: Row, b: Row) =>
  String(a.movement_date).localeCompare(String(b.movement_date)) || a.id - b.id;
export async function movementReport(
  params: Params,
  context: string,
): Promise<InventoryPrintReport> {
  const data = await allInventoryRows("/inventory/movements", params);
  const columns: PrintColumn[] = [
    { label: "Date" },
    { label: "Source document" },
    { label: "Item code", code: true },
    { label: "Item name" },
    { label: "Warehouse" },
    { label: "Event" },
    { label: "Quantity", numeric: true },
    { label: "Unit cost", numeric: true },
    { label: "Value", numeric: true },
  ];
  const value = (items: Row[], event: string) =>
    total(
      items.filter((r) => direction(r) === event),
      "movement_value",
    );
  return {
    title: "Stock Movement",
    context,
    columns,
    rowCount: data.items.length,
    groups: grouped(data.items, accountName).map(([, items]) => ({
      title: items[0].inventory_account_name || "Unmapped inventory account",
      rows: items
        .sort(chronological)
        .map((r) => [
          r.movement_date,
          reference(r),
          r.product_code,
          r.product_name,
          r.warehouse_name,
          direction(r),
          num(r.quantity),
          money(r.unit_cost),
          money(r.movement_value),
        ]),
      footer: [
        "Subtotal net value",
        null,
        null,
        null,
        null,
        null,
        null,
        null,
        money(value(items, "IN") - value(items, "OUT")),
      ],
    })),
    summary: `IN value: ${money(value(data.items, "IN"))} · OUT value: ${money(value(data.items, "OUT"))}`,
    footer: [
      "Grand total net value",
      null,
      null,
      null,
      null,
      null,
      null,
      null,
      money(value(data.items, "IN") - value(data.items, "OUT")),
    ],
  };
}

export async function stockCardReport(
  params: Params,
  context: string,
): Promise<InventoryPrintReport> {
  const dates = {
    date_from: "2026-01-01",
    date_to: new Date().toLocaleDateString("en-CA", {
      timeZone: "Asia/Jakarta",
    }),
  };
  const filters = {
    ...params,
    date_from: params.date_from || dates.date_from,
    date_to: params.date_to || dates.date_to,
  };
  const [data, stockData] = await Promise.all([
    allInventoryRows("/inventory/movements", filters),
    allInventoryRows("/inventory", {
      warehouse_id: params.warehouse_id,
      account_id: params.account_id,
      as_of: filters.date_to,
    }),
  ]);
  const stock = stockData.items.filter(
    (r) => !params.product_id || r.product_id === params.product_id,
  );
  let details: any[] = [{ ...data, product_id: params.product_id }];
  if (!params.product_id && (data.items.length || stock.length)) {
    // The API calculates true running balances only when an item is selected.
    // Fetch item histories with bounded concurrency, preserving all account/date filters.
    const ids = [
      ...new Set([...data.items, ...stock].map((r) => r.product_id)),
    ];
    details = [];
    let cursor = 0;
    await Promise.all(
      Array.from({ length: Math.min(4, ids.length) }, async () => {
        while (cursor < ids.length) {
          const id = ids[cursor++];
          details.push({
            ...(await allInventoryRows("/inventory/movements", {
              ...filters,
              product_id: id,
            })),
            product_id: id,
          });
        }
      }),
    );
    const actual = details.flatMap((d) => d.items).map((r) => r.id);
    const actualIds = new Set(actual);
    if (
      actual.length !== data.items.length ||
      actualIds.size !== data.items.length ||
      data.items.some((r) => !actualIds.has(r.id))
    )
      throw new Error(
        "Stock history changed while preparing the report. Please retry.",
      );
  }
  const groups: PrintGroup[] = [];
  const seen = new Set<string>();
  for (const detail of details) {
    for (const [, items] of grouped(
      detail.items,
      (r: Row) => `${r.product_id}:${r.warehouse_id}`,
    )) {
      items.sort(chronological);
      const item = items[0];
      seen.add(`${item.product_id}:${item.warehouse_id}`);
      const balance = detail.history_balances?.find(
        (b: any) => b.warehouse_id === item.warehouse_id,
      );
      if (!balance || items.some((r) => r.running_quantity == null))
        throw new Error(
          "Stock-card balances are unavailable for an item. Please retry.",
        );
      groups.push({
        title: `${item.product_code} — ${item.product_name} · ${item.warehouse_name}`,
        detail: `Unit: ${stock.find((r) => r.product_id === item.product_id)?.uom || "—"} · Opening quantity: ${num(balance.opening_quantity)} · Closing quantity: ${num(balance.closing_quantity)}`,
        rows: items.map((r) => [
          r.movement_date,
          reference(r),
          Number(r.in_quantity) ? num(r.in_quantity) : "—",
          Number(r.out_quantity) ? num(r.out_quantity) : "—",
          num(r.running_quantity),
          money(
            r.movement_type === "OUT"
              ? -Number(r.movement_value)
              : r.movement_value,
          ),
        ]),
        footer: [
          "Period movement",
          null,
          num(total(items, "in_quantity")),
          num(total(items, "out_quantity")),
          null,
          money(
            items.reduce(
              (sum, r) =>
                sum +
                (direction(r) === "OUT" ? -1 : 1) * Number(r.movement_value),
              0,
            ),
          ),
        ],
      });
    }
  }
  for (const item of stock) {
    if (seen.has(`${item.product_id}:${item.warehouse_id}`)) continue;
    const detail = details.find((d) => d.product_id === item.product_id);
    const balance = detail?.history_balances?.find(
      (b: any) => b.warehouse_id === item.warehouse_id,
    );
    if (!balance)
      throw new Error(
        "Stock-card balances are unavailable for an item. Please retry.",
      );
    groups.push({
      title: `${item.product_code} — ${item.product_name} · ${item.warehouse_name}`,
      detail: `Unit: ${stock.find((r) => r.product_id === item.product_id)?.uom || "—"} · Opening quantity: ${num(balance.opening_quantity)} · Closing quantity: ${num(balance.closing_quantity)}`,
      rows: [],
      footer: [
        "No matching movements",
        null,
        null,
        null,
        num(balance.closing_quantity),
        null,
      ],
    });
  }
  groups.sort((a, b) => a.title.localeCompare(b.title));
  return {
    title: "Stock Card",
    context: `${context} · Period: ${filters.date_from} – ${filters.date_to}`,
    rowCount: data.items.length,
    columns: [
      { label: "Date" },
      { label: "Source document" },
      { label: "IN", numeric: true },
      { label: "OUT", numeric: true },
      { label: "Running quantity", numeric: true },
      { label: "Movement value", numeric: true },
    ],
    groups,
    footer: [
      "Grand total movement value",
      null,
      null,
      null,
      null,
      money(
        data.items.reduce(
          (sum, r) =>
            sum + (direction(r) === "OUT" ? -1 : 1) * Number(r.movement_value),
          0,
        ),
      ),
    ],
  };
}

export type InventoryDocumentKind =
  "adjustments" | "opnames" | "requests" | "putaway";
export async function inventoryDocumentReport(
  kind: InventoryDocumentKind,
  params: Params,
  context: string,
): Promise<InventoryPrintReport> {
  const configs = {
    adjustments: {
      path: "/stock-adjustments",
      title: "Stock Adjustments",
      columns: [
        "Number",
        "Date",
        "Warehouse",
        "Reason",
        "Status",
        "Value",
        "Created by",
      ],
      keys: [
        "adjustment_number",
        "adjustment_date",
        "warehouse_name",
        "reason",
        "status",
        "total_adjustment_value",
        "created_by_name",
      ],
    },
    opnames: {
      path: "/stock-opnames",
      title: "Stock Opname",
      columns: [
        "Number",
        "Count date",
        "Warehouse",
        "Location",
        "Items",
        "Variance",
        "Status",
      ],
      keys: [
        "opname_number",
        "count_date",
        "warehouse_name",
        "location_name",
        "total_items",
        "total_variance_quantity",
        "status",
      ],
    },
    requests: {
      path: "/store-requests",
      title: "Store Requests",
      columns: [
        "Number",
        "Date",
        "Requester",
        "Warehouse",
        "Department",
        "Remaining",
        "Status",
      ],
      keys: [
        "sr_number",
        "request_date",
        "requester_name",
        "warehouse_name",
        "department_name",
        "total_remaining_quantity",
        "status",
      ],
    },
    putaway: {
      path: "/put-away",
      title: "Put Away",
      columns: ["Number", "Receipt", "Warehouse", "Status"],
      keys: ["putaway_number", "receipt_number", "warehouse_name", "status"],
    },
  };
  const config = configs[kind];
  const items =
    kind === "putaway"
      ? (await api.get<Row[]>(config.path)).data
      : (await allInventoryRows(config.path, params)).items;
  const numericKeys = new Set([
    "total_items",
    "total_variance_quantity",
    "total_remaining_quantity",
    "total_adjustment_value",
  ]);
  return {
    title: config.title,
    context,
    rowCount: items.length,
    columns: config.columns.map((label, index) => ({
      label,
      numeric: numericKeys.has(config.keys[index]),
    })),
    groups: [
      {
        title: config.title,
        rows: items.map((r) =>
          config.keys.map((key) =>
            key === "total_adjustment_value"
              ? money(r[key])
              : numericKeys.has(key)
                ? num(r[key])
                : r[key],
          ),
        ),
      },
    ],
  };
}
