import Button from "@/components/ui/Button";

import type {
  SupplierProduct,
} from "../typesSupplierProduct";

interface Props {
  rows?: SupplierProduct[];

  onDelete?: (
    row: SupplierProduct
  ) => void;
}

export default function SupplierProductTable({
  rows = [],
  onDelete,
}: Props) {
  return (
    <table className="w-full border-collapse">
      <thead>
        <tr className="border-b">
          <th className="p-3 text-left">
            Product
          </th>

          <th className="p-3 text-left">
            Purchase UOM
          </th>

          <th className="p-3 text-right">
            Last Price
          </th>

          <th className="p-3 text-right">
            Lead Time
          </th>

          <th className="p-3 text-center">
            Preferred
          </th>

          <th />
        </tr>
      </thead>

      <tbody>
        {rows.map((row) => (
          <tr
            key={row.id}
            className="border-b"
          >
            <td className="p-3">
              {row.product_name}
            </td>

            <td className="p-3">
              {row.purchase_uom}
            </td>

            <td className="p-3 text-right">
              {row.last_price.toLocaleString()}
            </td>

            <td className="p-3 text-right">
              {row.lead_time} day(s)
            </td>

            <td className="text-center">
              {row.preferred
                ? "✓"
                : ""}
            </td>

            <td className="text-right">
              <Button
                size="sm"
                variant="danger"
                onClick={() =>
                  onDelete?.(row)
                }
              >
                Remove
              </Button>
            </td>
          </tr>
        ))}

        {rows.length === 0 && (
          <tr>
            <td
              colSpan={6}
              className="p-8 text-center"
            >
              No Products Assigned
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}
