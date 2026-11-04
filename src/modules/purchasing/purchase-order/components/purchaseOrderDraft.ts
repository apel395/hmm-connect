import { todayLocal } from "@/utils/dateConstraints";
import type { PurchaseOrderItemRow } from "./PurchaseOrderItems";
import type { MarketListOption } from "./MarketListPicker";

export type CreationType = "FROM_PR" | "FROM_ML" | "DIRECT";
export type ProductOption = {
  id: number;
  code: string;
  name: string;
  description?: string | null;
  uom: string;
};

export interface PurchaseOrderDraft {
  creationType: CreationType;
  supplierId?: number;
  selectedPRs: any[];
  selectedML?: MarketListOption;
  businessUnitId?: number;
  departmentId?: number;
  locationId?: number;
  orderDate: string;
  expectedDate: string;
  notes: string;
  products: ProductOption[];
  items: PurchaseOrderItemRow[];
}

export function validPurchaseOrderDraft(
  value: unknown,
): value is PurchaseOrderDraft {
  if (!value || typeof value !== "object") return false;
  const draft = value as PurchaseOrderDraft;
  return (
    ["FROM_PR", "FROM_ML", "DIRECT"].includes(draft.creationType) &&
    typeof draft.orderDate === "string" &&
    typeof draft.expectedDate === "string" &&
    typeof draft.notes === "string" &&
    Array.isArray(draft.selectedPRs) &&
    Array.isArray(draft.products) &&
    Array.isArray(draft.items) &&
    draft.items.every(
      (item) =>
        item &&
        typeof item.quantity === "number" &&
        Number.isFinite(item.quantity) &&
        typeof item.unit_price === "number" &&
        Number.isFinite(item.unit_price),
    )
  );
}

export function initialPurchaseOrderDraft(
  initialData?: any,
): PurchaseOrderDraft {
  if (!initialData) {
    return {
      creationType: "FROM_PR",
      supplierId: undefined,
      selectedPRs: [],
      selectedML: undefined,
      businessUnitId: undefined,
      departmentId: undefined,
      locationId: undefined,
      orderDate: todayLocal(),
      expectedDate: "",
      notes: "",
      products: [],
      items: [],
    };
  }

  const creationType: CreationType =
    initialData.creation_type === "FROM_PR"
      ? "FROM_PR"
      : initialData.market_list_id
        ? "FROM_ML"
        : "DIRECT";
  const selectedPRs =
    creationType === "FROM_PR"
      ? (initialData.source_purchase_requisitions?.length
          ? initialData.source_purchase_requisitions
          : [
              {
                id: initialData.source_pr_id,
                pr_number: initialData.source_pr_number,
                business_unit_id: initialData.business_unit_id,
                business_unit_name: initialData.business_unit_name,
                department_id: initialData.department_id,
                department_name: initialData.department_name,
                location_id: initialData.location_id,
                location_name: initialData.location_name,
              },
            ]
        ).filter((item: any) => item.id)
      : [];
  return {
    creationType,
    supplierId: initialData.supplier_id ?? undefined,
    selectedPRs,
    selectedML: undefined,
    businessUnitId: initialData.business_unit_id ?? undefined,
    departmentId: initialData.department_id ?? undefined,
    locationId: initialData.location_id ?? undefined,
    orderDate: initialData.order_date ?? todayLocal(),
    expectedDate: initialData.expected_date ?? "",
    notes: initialData.notes ?? "",
    products: (initialData.items ?? []).map((item: any) => ({
      id: Number(item.product_id),
      code: item.product_code ?? "",
      name: item.product_name ?? "",
      description: item.description ?? "",
      uom: item.uom ?? "",
    })),
    items: (initialData.items ?? []).map((item: any) => ({
      product_id: item.product_id,
      product_code: item.product_code,
      product_name: item.product_name,
      description: item.description ?? "",
      uom: item.uom ?? "",
      requested_quantity: Number(item.quantity),
      remaining_quantity: Number(item.remaining_quantity ?? item.quantity),
      quantity: Number(item.quantity),
      unit_price: Number(item.unit_price),
      purchase_requisition_item_id: item.purchase_requisition_item_id ?? null,
      market_list_item_id: item.market_list_item_id ?? null,
      source_pr_number: item.source_pr_number ?? initialData.source_pr_number,
      source_ml_number:
        item.source_market_list_number ?? initialData.source_market_list_number,
    })),
  };
}
