import { useQuery } from "@tanstack/react-query";

import {
  getInventory,
} from "../features/inventory/inventoryApi";

export default function InventoryPage() {
  const inventoryQuery = useQuery({
    queryKey: ["inventory"],
    queryFn: getInventory,
  });

  const inventory = inventoryQuery.data ?? [];

  const totalStock = inventory.reduce(
    (total, item) =>
      total + Number(item.quantity),
    0,
  );

  const totalValue = inventory.reduce(
    (total, item) =>
      total +
      Number(item.quantity) *
        Number(item.average_cost),
    0,
  );

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">
          Inventory
        </h1>

        <p className="mt-1 text-sm text-slate-500">
          View current stock levels and inventory value.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-500">
            Products in stock
          </p>

          <p className="mt-2 text-2xl font-semibold text-slate-900">
            {inventory.length}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-500">
            Total quantity
          </p>

          <p className="mt-2 text-2xl font-semibold text-slate-900">
            {totalStock.toFixed(2)}
          </p>
        </div>

        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-500">
            Inventory value
          </p>

          <p className="mt-2 text-2xl font-semibold text-slate-900">
            {totalValue.toFixed(2)}
          </p>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white">
        <div className="flex items-center justify-between border-b border-slate-200 p-6">
          <h2 className="font-semibold text-slate-900">
            Stock
          </h2>

          <span className="text-sm text-slate-500">
            {inventory.length} products
          </span>
        </div>

        {inventoryQuery.isLoading && (
          <div className="p-8 text-center text-sm text-slate-500">
            Loading inventory...
          </div>
        )}

        {inventoryQuery.isError && (
          <div className="p-8 text-center text-sm text-red-600">
            Failed to load inventory.
          </div>
        )}

        {!inventoryQuery.isLoading &&
          !inventoryQuery.isError &&
          inventory.length === 0 && (
            <div className="p-8 text-center text-sm text-slate-500">
              No inventory yet.
            </div>
          )}

        {inventory.length > 0 && (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-slate-200 text-left">
                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Code
                  </th>

                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Product
                  </th>

                  <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Warehouse
                  </th>

                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Quantity
                  </th>

                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                    UOM
                  </th>

                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Average Cost
                  </th>

                  <th className="px-6 py-4 text-right text-xs font-semibold uppercase tracking-wide text-slate-500">
                    Stock Value
                  </th>
                </tr>
              </thead>

              <tbody>
                {inventory.map((item) => {
                  const stockValue =
                    Number(item.quantity) *
                    Number(item.average_cost);

                  return (
                    <tr
                      key={`${item.product_id}-${item.warehouse_id}`}
                      className="border-b border-slate-100 last:border-0 hover:bg-slate-50"
                    >
                      <td className="px-6 py-4 text-sm font-medium text-slate-900">
                        {item.code}
                      </td>

                      <td className="px-6 py-4 text-sm text-slate-700">
                        {item.name}
                      </td>

                      <td className="px-6 py-4 text-sm text-slate-600">
                        {item.warehouse_code} - {item.warehouse_name}
                      </td>

                      <td className="px-6 py-4 text-right text-sm font-medium text-slate-900">
                        {Number(item.quantity).toFixed(2)}
                      </td>

                      <td className="px-6 py-4 text-right text-sm text-slate-600">
                        {item.uom}
                      </td>

                      <td className="px-6 py-4 text-right text-sm text-slate-600">
                        {Number(
                          item.average_cost,
                        ).toFixed(2)}
                      </td>

                      <td className="px-6 py-4 text-right text-sm font-medium text-slate-900">
                        {stockValue.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
