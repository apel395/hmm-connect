import type { ProductComboboxOption } from "@/components/form/ProductCombobox";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const optionalNumber = (value: unknown) =>
  value === undefined || (typeof value === "number" && Number.isFinite(value));

export type StockOpnameDraft = {
  warehouseId?: number;
  locationId?: number;
  departmentId?: number;
  notes: string;
};

export function validStockOpnameDraft(
  value: unknown,
): value is StockOpnameDraft {
  return (
    isRecord(value) &&
    optionalNumber(value.warehouseId) &&
    optionalNumber(value.locationId) &&
    optionalNumber(value.departmentId) &&
    typeof value.notes === "string"
  );
}

export type StoreRequestItemDraft = {
  product_id?: number;
  quantity: number;
  product?: ProductComboboxOption;
};

export type StoreRequestDraft = {
  requestDate: string;
  businessUnitId?: number;
  departmentId?: number;
  locationId?: number;
  warehouseId?: number;
  notes: string;
  items: StoreRequestItemDraft[];
};

export function validStoreRequestDraft(
  value: unknown,
): value is StoreRequestDraft {
  return (
    isRecord(value) &&
    typeof value.requestDate === "string" &&
    typeof value.notes === "string" &&
    [
      value.businessUnitId,
      value.departmentId,
      value.locationId,
      value.warehouseId,
    ].every(optionalNumber) &&
    Array.isArray(value.items) &&
    value.items.every(
      (item) =>
        isRecord(item) &&
        optionalNumber(item.product_id) &&
        typeof item.quantity === "number" &&
        Number.isFinite(item.quantity),
    )
  );
}

export type StockAdjustmentLineDraft = {
  key: number;
  product_id?: number;
  product_code?: string;
  product_name?: string;
  uom?: string;
  system_quantity: number;
  adjusted_quantity: number;
  unit_cost: number;
  reason: string;
};

export type StockAdjustmentDraft = {
  warehouseId?: number;
  adjustmentDate: string;
  reason: string;
  notes: string;
  lines: StockAdjustmentLineDraft[];
};

export function validStockAdjustmentDraft(
  value: unknown,
): value is StockAdjustmentDraft {
  return (
    isRecord(value) &&
    optionalNumber(value.warehouseId) &&
    typeof value.adjustmentDate === "string" &&
    typeof value.reason === "string" &&
    typeof value.notes === "string" &&
    Array.isArray(value.lines) &&
    value.lines.every(
      (line) =>
        isRecord(line) &&
        typeof line.key === "number" &&
        optionalNumber(line.product_id) &&
        typeof line.system_quantity === "number" &&
        typeof line.adjusted_quantity === "number" &&
        typeof line.unit_cost === "number" &&
        typeof line.reason === "string",
    )
  );
}
