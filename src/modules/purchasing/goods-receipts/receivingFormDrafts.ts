import type { ReceivingBilling } from "./billing";

const object = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const billingIsValid = (value: unknown): value is ReceivingBilling =>
  object(value) &&
  typeof value.supplier_invoice_number === "string" &&
  typeof value.other_fee_description === "string" &&
  typeof value.discount_amount === "number" &&
  typeof value.shipping_fee_amount === "number";

const linesAreValid = (value: unknown) =>
  Array.isArray(value) &&
  value.every(
    (line) =>
      object(line) &&
      typeof line.quantity === "number" &&
      typeof line.unit_cost === "number",
  );

export const validReceivingLinesDraft = <
  T extends {
    lines: { quantity: number; unit_cost: number }[];
    billing: ReceivingBilling;
  },
>(
  value: unknown,
): value is T =>
  object(value) &&
  linesAreValid(value.lines) &&
  billingIsValid(value.billing) &&
  typeof value.receivedAt === "string" &&
  typeof value.notes === "string";

export const validReceivingProductLinesDraft = <
  T extends {
    lines: { quantity: number; unit_cost: number }[];
    billing: ReceivingBilling;
    productRows: unknown[];
  },
>(value: unknown): value is T =>
  validReceivingLinesDraft<T>(value) && Array.isArray(value.productRows);

export const validReceivingEditDraft = <
  T extends {
    items: { quantity: number; unit_cost: number }[];
    billing: ReceivingBilling;
  },
>(
  value: unknown,
): value is T =>
  object(value) &&
  linesAreValid(value.items) &&
  billingIsValid(value.billing) &&
  Array.isArray(value.productRows) &&
  typeof value.receivedAt === "string" &&
  typeof value.notes === "string";

export const restoredReceivingQuantity = (remaining: number, saved: number) =>
  Math.min(Math.max(0, remaining), Math.max(0, saved));
