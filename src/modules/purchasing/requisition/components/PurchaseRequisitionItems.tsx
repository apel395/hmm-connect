import Button from "@/components/ui/Button";
import { Trash2 } from "lucide-react";
import Badge from "@/components/ui/Badge";
import CurrencyInput from "@/components/form/CurrencyInput";
import ProductCombobox, {
  type ProductComboboxOption,
} from "@/components/form/ProductCombobox";
import QuantityInput from "@/components/form/QuantityInput";

export interface Product extends ProductComboboxOption {
  tax_category?:
    "STANDARD" | "EXEMPT" | "NON_VAT" | "SPECIAL" | "REVIEW_REQUIRED";
}
export interface PurchaseRequisitionItemRow {
  product_id: number;
  quantity: number;
  estimated_price: number;
}
interface Props {
  items: PurchaseRequisitionItemRow[];
  products: Product[];
  loadingProducts?: boolean;
  onChange: (rows: PurchaseRequisitionItemRow[]) => void;
  onProductLoaded?: (product: Product) => void;
}

const money = (value: number) =>
  value.toLocaleString("en-US", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });

export default function PurchaseRequisitionItems({
  items,
  products,
  loadingProducts,
  onChange,
  onProductLoaded,
}: Props) {
  const updateRow = (
    index: number,
    field: keyof PurchaseRequisitionItemRow,
    value: number,
  ) =>
    onChange(
      items.map((row, i) => (i === index ? { ...row, [field]: value } : row)),
    );
  const addRow = () =>
    onChange([...items, { product_id: 0, quantity: 1, estimated_price: 0 }]);
  const removeRow = (index: number) =>
    items.length > 1 && onChange(items.filter((_, i) => i !== index));
  const selectProduct = (index: number, selected: Product) => {
    onProductLoaded?.(selected);
    const historyPrice =
      selected.last_purchase_price === null ||
      selected.last_purchase_price === undefined
        ? null
        : Number(selected.last_purchase_price);
    onChange(
      items.map((row, i) =>
        i === index
          ? {
              ...row,
              product_id: selected.id,
              estimated_price:
                historyPrice !== null && Number.isFinite(historyPrice)
                  ? historyPrice
                  : row.estimated_price,
            }
          : row,
      ),
    );
  };

  const totals = items.reduce(
    (acc, row) => {
      const product = products.find((item) => item.id === row.product_id);
      const subtotal = row.quantity * row.estimated_price;
      const rate = product?.is_taxable ? Number(product.tax_rate ?? 0) : 0;
      const tax = (subtotal * rate) / 100;
      acc.subtotal += subtotal;
      acc.tax += tax;
      acc.total += subtotal + tax;
      return acc;
    },
    { subtotal: 0, tax: 0, total: 0 },
  );

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-800">
        Purchase Requisition is for non-market items. VEGETABLES and FRUIT are
        requested through Market List.
      </div>
      <div className="overflow-x-auto rounded-lg border border-slate-200">
        <table className="table-grid w-full min-w-[860px] table-fixed text-sm">
          <thead className="bg-slate-50">
            <tr>
              <th className="w-[30%] p-2 text-left">Product</th>
              <th className="w-[8%] p-2 text-left">UOM</th>
              <th className="w-[12%] p-2 text-right">Qty</th>
              <th className="w-[20%] p-2 text-right">Estimated Price</th>
              <th className="w-[16%] p-2 text-right">Line Total</th>
              <th className="w-[10%] p-2 text-left">Tax</th>
              <th className="w-[4%]" aria-label="Actions" />
            </tr>
          </thead>
          <tbody>
            {items.map((row, index) => {
              const product = products.find(
                (item) => item.id === row.product_id,
              );
              const subtotal = row.quantity * row.estimated_price;
              const rate = product?.is_taxable
                ? Number(product.tax_rate ?? 0)
                : 0;
              const tax = (subtotal * rate) / 100;
              const reviewRequired =
                product?.tax_category === "REVIEW_REQUIRED";
              return (
                <tr
                  key={index}
                  className={
                    reviewRequired ? "border-t bg-amber-50/60" : "border-t"
                  }
                >
                  <td className="p-2">
                    <ProductCombobox
                      value={row.product_id || undefined}
                      products={products}
                      remote
                      excludeMarket
                      requireTaxReady
                      disabled={loadingProducts}
                      onChange={(productId) =>
                        updateRow(index, "product_id", productId)
                      }
                      onSelect={(selected) =>
                        selectProduct(index, selected as Product)
                      }
                    />
                  </td>
                  <td className="p-2 text-xs text-slate-700">
                    {product?.uom ?? product?.usage_uom ?? "—"}
                  </td>
                  <td className="p-2">
                    <QuantityInput
                      value={row.quantity}
                      min={0.01}
                      onValueChange={(value) =>
                        updateRow(index, "quantity", value)
                      }
                    />
                  </td>
                  <td className="p-2">
                    <CurrencyInput
                      value={row.estimated_price}
                      onValueChange={(value) =>
                        updateRow(index, "estimated_price", value)
                      }
                    />
                    {product?.last_purchase_price !== null &&
                    product?.last_purchase_price !== undefined ? (
                      <div className="mt-1 text-[11px] text-slate-500">
                        Last PO: Rp {money(Number(product.last_purchase_price))}
                      </div>
                    ) : null}
                  </td>
                  <td className="p-2 text-right tabular-nums">
                    <div className="font-semibold">{money(subtotal + tax)}</div>
                    <div className="mt-0.5 text-[10px] text-slate-500">
                      Base {money(subtotal)} · PPN {money(tax)}
                    </div>
                  </td>
                  <td className="p-2">
                    {reviewRequired ? (
                      <Badge variant="warning">Tax Review</Badge>
                    ) : product?.is_taxable ? (
                      <Badge variant="info">PPN {rate}%</Badge>
                    ) : (
                      <Badge variant="secondary">Non PPN</Badge>
                    )}
                  </td>
                  <td className="p-1 text-center">
                    <button
                      type="button"
                      disabled={items.length === 1}
                      aria-label="Remove requisition item"
                      title="Remove item"
                      className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-700 disabled:cursor-not-allowed disabled:opacity-30"
                      onClick={() => removeRow(index)}
                    >
                      <Trash2 aria-hidden="true" className="h-4 w-4" />
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {items.some(
        (row) =>
          products.find((product) => product.id === row.product_id)
            ?.tax_category === "REVIEW_REQUIRED",
      ) && (
        <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          <strong>Finance tax review required.</strong> One or more selected
          items have not been classified in Item Master. The backend will block
          submission/approval until Finance completes the tax profile.
        </div>
      )}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <Button type="button" onClick={addRow}>
          Add Item
        </Button>
        <div className="w-full rounded-lg border bg-slate-50 px-4 py-3 text-sm sm:w-auto sm:min-w-72">
          <div className="flex justify-between gap-8 text-slate-600">
            <span>Subtotal</span>
            <span className="tabular-nums">{money(totals.subtotal)}</span>
          </div>
          <div className="mt-1 flex justify-between gap-8 text-slate-600">
            <span>PPN</span>
            <span className="tabular-nums">{money(totals.tax)}</span>
          </div>
          <div className="mt-3 flex justify-between gap-8 border-t pt-3 text-base font-bold">
            <span>Grand Total</span>
            <span className="tabular-nums">{money(totals.total)}</span>
          </div>
          <div className="mt-2 text-xs text-slate-500">
            Estimate only. Backend recalculates the final tax snapshot.
          </div>
        </div>
      </div>
    </div>
  );
}
