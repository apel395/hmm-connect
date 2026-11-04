import { todayLocal } from "@/utils/dateConstraints";
import type { ProductComboboxOption } from "@/components/form/ProductCombobox";

export type MarketListRow = {
  product_id: number;
  quantity: number;
  estimated_price: number;
};
export type MarketListProduct = ProductComboboxOption & {
  tax_category?: string;
};

export interface MarketListDraft {
  bu?: number;
  dept?: number;
  loc?: number;
  requestDate: string;
  expiry: string;
  notes: string;
  rows: MarketListRow[];
  products: MarketListProduct[];
}

export function validMarketListDraft(value: unknown): value is MarketListDraft {
  if (!value || typeof value !== "object") return false;
  const draft = value as MarketListDraft;
  return (
    typeof draft.requestDate === "string" &&
    typeof draft.expiry === "string" &&
    typeof draft.notes === "string" &&
    Array.isArray(draft.products) &&
    Array.isArray(draft.rows) &&
    draft.rows.every(
      (row) =>
        row &&
        Number.isFinite(row.product_id) &&
        Number.isFinite(row.quantity) &&
        Number.isFinite(row.estimated_price),
    )
  );
}

export function initialMarketListDraft(initialData?: any): MarketListDraft {
  if (!initialData)
    return {
      bu: undefined,
      dept: undefined,
      loc: undefined,
      requestDate: todayLocal(),
      expiry: "",
      notes: "",
      rows: [{ product_id: 0, quantity: 1, estimated_price: 0 }],
      products: [],
    };
  return {
    bu: initialData.business_unit_id,
    dept: initialData.department_id,
    loc: initialData.location_id,
    requestDate: initialData.request_date || todayLocal(),
    expiry: initialData.expiry_date || "",
    notes: initialData.notes || "",
    rows: (initialData.items || []).map((item: any) => ({
      product_id: Number(item.product_id),
      quantity: Number(item.quantity),
      estimated_price: Number(item.estimated_price),
    })),
    products: (initialData.items || []).map((item: any) => ({
      id: Number(item.product_id),
      code: item.product_code,
      name: item.product_name,
      uom: item.uom,
      is_taxable: item.is_taxable,
      tax_rate: item.tax_rate,
      tax_category: item.tax_category,
    })),
  };
}
