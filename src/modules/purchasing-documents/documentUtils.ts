import axios from "axios";

interface ValidationIssue {
  loc?: Array<string | number>;
  msg?: string;
}

export function purchasingDocumentError(error: unknown): string {
  if (!axios.isAxiosError(error)) return "Unable to complete the document request.";
  const data = error.response?.data as
    | { detail?: string | ValidationIssue[] }
    | undefined;
  if (Array.isArray(data?.detail)) {
    const message = data.detail
      .map((item) => {
        const field = item.loc?.filter((part) => part !== "body").join(".");
        return [field, item.msg].filter(Boolean).join(": ");
      })
      .filter(Boolean)
      .join("; ");
    if (message) return message;
  }
  if (typeof data?.detail === "string") return data.detail;
  if (error.response?.status === 403) return "You do not have access to purchasing documents.";
  if (error.response?.status === 404) return "The purchasing document was not found.";
  if (error.response?.status === 409) return "A conflicting purchasing document already exists.";
  if (error.response?.status === 422) return "Please check the document fields.";
  if (error.response?.status && error.response.status >= 500) {
    return "The server could not process the purchasing document.";
  }
  return "Unable to complete the document request.";
}

export function formatMoney(value?: string | null, currency = "IDR"): string {
  if (value === null || value === undefined || value === "") return "—";
  return new Intl.NumberFormat("id-ID", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(Number(value));
}

export function addDecimalStrings(left: string, right: string): string {
  const toHundredths = (value: string): bigint | null => {
    const normalized = value.trim();
    if (!/^\d+(\.\d{0,2})?$/.test(normalized)) return null;
    const [whole, fraction = ""] = normalized.split(".");
    return BigInt(whole) * 100n + BigInt(fraction.padEnd(2, "0"));
  };
  const leftValue = toHundredths(left);
  const rightValue = toHundredths(right);
  if (leftValue === null || rightValue === null) return "";
  const total = leftValue + rightValue;
  return `${total / 100n}.${String(total % 100n).padStart(2, "0")}`;
}
