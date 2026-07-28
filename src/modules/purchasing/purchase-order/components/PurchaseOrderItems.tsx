import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";

export interface SupplierProduct {

  id: number;

  product_id: number;

  product_code: string;

  product_name: string;

  product_uom: string;

  product_usage_uom?: string;

  conversion?: number;

  supplier_sku?: string;

  supplier_price?: number;

  lead_time_days?: number;

  is_preferred?: boolean;

}

export interface PurchaseOrderItemRow {

  product_id: number;

  quantity: number;

  unit_price: number;

  purchase_requisition_item_id?: number | null;

}

interface Props {

  items: PurchaseOrderItemRow[];

  supplierProducts: SupplierProduct[];

  onChange: (
    rows: PurchaseOrderItemRow[]
  ) => void;

}

export default function PurchaseOrderItems({

  items,

  supplierProducts,

  onChange,

}: Props) {

  function updateRow(

    index: number,

    field: keyof PurchaseOrderItemRow,

    value: any,

  ) {

    const rows = [...items];

    rows[index] = {

      ...rows[index],

      [field]: value,

    };

    if (field === "product_id") {

      const product =
        supplierProducts.find(
          (p) =>
            p.product_id === Number(value)
        );

      if (product) {

        rows[index].unit_price =
          Number(
            product.supplier_price ?? 0
          );

      }

    }

    onChange(rows);

  }

  function addRow() {

    onChange([

      ...items,

      {

        product_id: 0,

        quantity: 1,

        unit_price: 0,

        purchase_requisition_item_id: null,

      },

    ]);

  }

  function removeRow(
    index: number
  ) {

    onChange(

      items.filter(
        (_, i) => i !== index
      )

    );

  }

  return (

    <div className="space-y-4">

      <div className="overflow-x-auto rounded-lg border border-slate-200">

        <table className="min-w-[1100px] w-full">

          <thead className="bg-slate-50">

            <tr>

              <th className="p-3 text-left">
                Product
              </th>

              <th className="p-3 text-center">
                SKU
              </th>

              <th className="p-3 text-center">
                Purchase UOM
              </th>

              <th className="p-3 text-center">
                Usage UOM
              </th>

              <th className="p-3 text-center">
                Conversion
              </th>

              <th className="p-3 text-center">
                Lead Time
              </th>

              <th className="p-3 text-center">
                Qty
              </th>

              <th className="p-3 text-center">
                Unit Price
              </th>

              <th className="p-3 text-right">
                Amount
              </th>

              <th className="w-24" />

            </tr>

          </thead>

          <tbody>

            {items.map((row, index) => {

              const product =
                supplierProducts.find(
                  (x) =>
                    x.product_id === row.product_id
                );

              return (

                <tr
                  key={index}
                  className="border-t"
                >

                  <td className="p-2">

                    <select

                      className="w-full rounded-md border border-slate-300 p-2"

                      value={row.product_id}

                      onChange={(e) =>

                        updateRow(

                          index,

                          "product_id",

                          Number(
                            e.target.value
                          ),

                        )

                      }

                    >

                      <option value={0}>
                        Select Product
                      </option>

                      {supplierProducts.map((p) => (

                        <option

                          key={p.id}

                          value={p.product_id}

                        >

                          {p.product_code}
                          {" - "}
                          {p.product_name}

                        </option>

                      ))}

                    </select>

                  </td>

                  <td className="text-center">

                    {product?.supplier_sku ?? "-"}

                  </td>

                  <td className="text-center">

                    {product?.product_uom ?? "-"}

                  </td>

                  <td className="text-center">

                    {product?.product_usage_uom ?? "-"}

                  </td>

                  <td className="text-center">

                    {product?.conversion ?? "-"}

                  </td>

                  <td className="text-center">

                    {product?.lead_time_days ?? "-"}

                  </td>

                  <td className="p-2">

                    <Input

                      type="number"

                      value={row.quantity}

                      onChange={(e) =>

                        updateRow(

                          index,

                          "quantity",

                          Number(
                            e.target.value
                          ),

                        )

                      }

                    />

                  </td>

                  <td className="p-2">

                    <Input

                      type="number"

                      value={row.unit_price}

                      onChange={(e) =>

                        updateRow(

                          index,

                          "unit_price",

                          Number(
                            e.target.value
                          ),

                        )

                      }

                    />

                  </td>

                  <td className="pr-4 text-right font-medium">

                    {(

                      row.quantity *
                      row.unit_price

                    ).toLocaleString(

                      "en-US",

                      {

                        minimumFractionDigits: 2,

                        maximumFractionDigits: 2,

                      },

                    )}

                  </td>

                  <td className="p-2">

                    <Button

                      variant="danger"

                      size="sm"

                      onClick={() =>
                        removeRow(index)
                      }

                    >

                      Remove

                    </Button>

                  </td>

                </tr>

              );

            })}

          </tbody>

        </table>

      </div>

      <div className="flex justify-start">

        <Button
          onClick={addRow}
        >

          Add Item

        </Button>

      </div>

    </div>

  );

}