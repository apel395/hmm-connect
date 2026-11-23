export type InvoiceFieldIssue = {
  path: string;
  message: string;
  actual?: string;
  expected?: string;
};

export type InvoiceErrorInfo = {
  message: string;
  code?: string;
  fields: InvoiceFieldIssue[];
  totals?: Record<string, unknown>;
};

const FALLBACK_MESSAGE = "Invoice could not be saved";

function pydanticPath(loc: unknown[]): string | null {
  const parts = loc.filter((part) => part !== "body" && part !== "query" && part !== "path");
  if (!parts.length) return null;
  let path = String(parts[0]);
  for (const part of parts.slice(1)) {
    path += typeof part === "number" ? `[${part}]` : `.${String(part)}`;
  }
  return path;
}

function toFieldIssue(value: unknown): InvoiceFieldIssue | null {
  if (!value || typeof value !== "object") return null;
  const item = value as Record<string, unknown>;
  const path = item.path ?? (Array.isArray(item.loc) ? pydanticPath(item.loc) : null);
  if (!path) return null;
  return {
    path: String(path),
    message: String(item.message ?? item.msg ?? "Check this value."),
    ...(item.actual == null ? {} : { actual: String(item.actual) }),
    ...(item.expected == null ? {} : { expected: String(item.expected) }),
  };
}

export function parseInvoiceErrorDetail(detail: unknown): InvoiceErrorInfo {
  if (typeof detail === "string") return { message: detail || FALLBACK_MESSAGE, fields: [] };

  if (Array.isArray(detail)) {
    const fields = detail.map(toFieldIssue).filter((issue): issue is InvoiceFieldIssue => issue !== null);
    const message = detail
      .map((item: any) => item?.msg ?? item?.message ?? String(item))
      .join("; ") || FALLBACK_MESSAGE;
    return { message, fields };
  }

  if (detail && typeof detail === "object") {
    const value = detail as Record<string, unknown>;
    const fields = Array.isArray(value.fields)
      ? value.fields.map(toFieldIssue).filter((issue): issue is InvoiceFieldIssue => issue !== null)
      : [];
    return {
      message: String(value.message ?? FALLBACK_MESSAGE),
      ...(value.code == null ? {} : { code: String(value.code) }),
      fields,
      ...(value.totals && typeof value.totals === "object" ? { totals: value.totals as Record<string, unknown> } : {}),
    };
  }

  return { message: FALLBACK_MESSAGE, fields: [] };
}

export function parseInvoiceError(error: unknown): InvoiceErrorInfo {
  if (error && typeof error === "object") {
    const candidate = error as Record<string, any>;
    if (candidate.response?.data?.detail !== undefined) return parseInvoiceErrorDetail(candidate.response.data.detail);
    if (candidate.detail !== undefined) return parseInvoiceErrorDetail(candidate.detail);
    if (candidate.message !== undefined) return parseInvoiceErrorDetail(candidate.message);
  }
  return parseInvoiceErrorDetail(error);
}

export function invoiceErrorMessage(error: unknown): string {
  const { message } = parseInvoiceError(error);
  if (/total amount|document total/i.test(message)) {
    return `${message} If you corrected PPN, update Document Total to the recalculated Invoice Total before saving.`;
  }
  return message;
}
