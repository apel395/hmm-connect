import { todayLocal } from "@/utils/dateConstraints";
import type {
  Product,
  PurchaseRequisitionItemRow,
} from "./PurchaseRequisitionItems";

export interface PurchaseRequisitionDraft {
  businessUnitId?: number;
  departmentId?: number;
  locationId?: number;
  requestDate: string;
  expiryDate: string;
  notes: string;
  products: Product[];
  items: PurchaseRequisitionItemRow[];
}

type UserDefaults = {
  business_unit_id?: number | null;
  default_business_unit_id?: number | null;
  department_id?: number | null;
  default_department_id?: number | null;
  location_id?: number | null;
  default_location_id?: number | null;
} | null;

export function validPurchaseRequisitionDraft(
  value: unknown,
): value is PurchaseRequisitionDraft {
  if (!value || typeof value !== "object") return false;
  const draft = value as PurchaseRequisitionDraft;
  return (
    typeof draft.requestDate === "string" &&
    typeof draft.expiryDate === "string" &&
    typeof draft.notes === "string" &&
    Array.isArray(draft.products) &&
    Array.isArray(draft.items) &&
    draft.items.every(
      (item) =>
        item &&
        Number.isFinite(item.product_id) &&
        Number.isFinite(item.quantity) &&
        Number.isFinite(item.estimated_price),
    )
  );
}

export function initialPurchaseRequisitionDraft(
  initialData?: any,
  user?: UserDefaults,
): PurchaseRequisitionDraft {
  if (!initialData)
    return {
      businessUnitId:
        user?.business_unit_id ?? user?.default_business_unit_id ?? undefined,
      departmentId:
        user?.department_id ?? user?.default_department_id ?? undefined,
      locationId: user?.location_id ?? user?.default_location_id ?? undefined,
      requestDate: todayLocal(),
      expiryDate: "",
      notes: "",
      products: [],
      items: [{ product_id: 0, quantity: 1, estimated_price: 0 }],
    };

  return {
    businessUnitId: initialData.business_unit_id ?? undefined,
    departmentId: initialData.department_id ?? undefined,
    locationId: initialData.location_id ?? undefined,
    requestDate: initialData.request_date ?? "",
    expiryDate: initialData.expiry_date ?? "",
    notes: initialData.notes ?? "",
    products: (initialData.items ?? []).map((item: any) => ({
      id: Number(item.product_id),
      code: item.product_code,
      name: item.product_name,
      uom: item.uom,
      tax_category: item.tax_category,
      is_taxable: item.is_taxable,
      tax_rate: item.tax_rate,
    })),
    items: (initialData.items ?? []).map((item: any) => ({
      product_id: Number(item.product_id),
      quantity: Number(item.quantity),
      estimated_price: Number(item.estimated_price),
    })),
  };
}
