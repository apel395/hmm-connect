/**
 * Supplier Payment amounts are stored as 2-decimal currency values by the API.
 * Sum integer cents rather than JavaScript floats before sending an exact
 * Decimal-validated payload.
 */
export function paymentCents(value: number | string | null | undefined): number {
  const number = Number(value ?? 0);
  if (!Number.isFinite(number)) throw new Error("Enter a valid payment amount.");
  const cents = Math.round(number * 100);
  if (!Number.isSafeInteger(cents)) throw new Error("Payment amount exceeds the supported range.");
  return cents;
}

export function fromPaymentCents(cents: number): number {
  return cents / 100;
}

export function sumPaymentAmounts(values: Array<number | string | null | undefined>): number {
  return fromPaymentCents(values.reduce<number>((total, value) => total + paymentCents(value), 0));
}

type PaymentMoneyFields = {
  bank_charge_amount: number;
  short_over_amount: number;
  allocations: Array<{ allocated_amount: number }>;
  funding_lines: Array<{ amount: number }>;
};

export function normalizePaymentForSave<T extends PaymentMoneyFields>(form: T) {
  const allocations = form.allocations.map((row) => ({
    ...row,
    allocated_amount: fromPaymentCents(paymentCents(row.allocated_amount)),
  }));
  const funding_lines = form.funding_lines.map((row) => ({
    ...row,
    amount: fromPaymentCents(paymentCents(row.amount)),
  }));
  return {
    ...form,
    total_amount: sumPaymentAmounts(allocations.map((row) => row.allocated_amount)),
    bank_charge_amount: fromPaymentCents(paymentCents(form.bank_charge_amount)),
    short_over_amount: fromPaymentCents(paymentCents(form.short_over_amount)),
    allocations,
    funding_lines,
  };
}

function errorText(value: unknown): string | null {
  if (typeof value === "string" && value.trim()) return value;
  if (value && typeof value === "object") {
    const entry = value as { msg?: unknown; message?: unknown };
    if (typeof entry.msg === "string" && entry.msg.trim()) return entry.msg;
    if (typeof entry.message === "string" && entry.message.trim()) return entry.message;
  }
  return null;
}

/** FastAPI 422 details can be arrays/objects, never pass them to a React toast. */
export function paymentSaveError(error: unknown): string {
  const detail = (error as { response?: { data?: { detail?: unknown } } } | null)
    ?.response?.data?.detail;
  if (Array.isArray(detail)) {
    const messages = detail.map(errorText).filter((message): message is string => Boolean(message));
    if (messages.length) return messages.join("; ");
  } else {
    const message = errorText(detail);
    if (message) return message;
  }
  return errorText(error) || "Payment could not be saved";
}
