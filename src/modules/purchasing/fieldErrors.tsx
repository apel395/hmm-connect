import { useEffect, useRef, useState } from "react";

export interface PurchasingFieldIssue {
  path: string;
  message: string;
}

export interface PurchasingErrorInfo {
  message: string;
  fields: Record<string, string>;
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function normalizeFieldPath(path: string): string {
  return path.replace(/\.(\d+)(?=\.|$)/g, "[$1]");
}

function pathFromLoc(loc: unknown[]): string {
  const parts = loc.filter((part) => part !== "body" && part !== "query" && part !== "path" && part !== "header");
  return parts.reduce<string>((path, part) => {
    if (typeof part === "number") return `${path}[${part}]`;
    return path ? `${path}.${part}` : String(part);
  }, "");
}

/** Normalizes both legacy string details and structured AP-style validation details. */
export function readPurchasingError(error: unknown): PurchasingErrorInfo {
  const detail = asRecord((error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail);
  const rawDetail = (error as { response?: { data?: { detail?: unknown } } })?.response?.data?.detail;
  const detailMessage = asRecord(rawDetail)?.message;
  const message = typeof rawDetail === "string"
    ? rawDetail
    : typeof detailMessage === "string"
      ? detailMessage
      : (error as { message?: string })?.message || "The request could not be completed.";

  const fields: Record<string, string> = {};
  const rawFields = detail?.fields;
  if (Array.isArray(rawFields)) {
    rawFields.forEach((entry) => {
      const field = asRecord(entry);
      const path = field?.path;
      const fieldMessage = field?.message;
      if (typeof path === "string" && typeof fieldMessage === "string") fields[normalizeFieldPath(path)] = fieldMessage;
    });
  }
  const legacyFields = Array.isArray(detail?.errors)
    ? detail.errors
    : Array.isArray(rawDetail)
      ? rawDetail
      : Array.isArray(detail?.detail)
        ? detail.detail
        : [];
  legacyFields.forEach((entry) => {
    const field = asRecord(entry);
    const path = field?.loc ?? field?.field ?? field?.path;
    const fieldMessage = field?.msg ?? field?.message;
    if (Array.isArray(path)) {
      if (typeof fieldMessage === "string") fields[normalizeFieldPath(pathFromLoc(path))] = fieldMessage;
    } else if (typeof path === "string" && typeof fieldMessage === "string") {
      fields[normalizeFieldPath(path)] = fieldMessage;
    }
  });
  return { message, fields };
}

/** Rewrites payload indexes to the row indexes actually rendered by a dialog. */
export function mapPurchasingFieldPaths(
  info: PurchasingErrorInfo,
  translate: (path: string) => string,
): PurchasingErrorInfo {
  const fields: Record<string, string> = {};
  Object.entries(info.fields).forEach(([path, fieldMessage]) => {
    fields[translate(path)] = fieldMessage;
  });
  return { ...info, fields };
}

/** Keeps a form's inline field messages and scrolls/focuses the first rejected control. */
export function usePurchasingFieldErrors(enabled = true) {
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [message, setMessage] = useState("");
  const wasEnabled = useRef(enabled);

  useEffect(() => {
    if (wasEnabled.current && !enabled) {
      setErrors({});
      setMessage("");
    }
    wasEnabled.current = enabled;
  }, [enabled]);

  useEffect(() => {
    if (!enabled || !message || Object.keys(errors).length === 0) return;
    const path = Object.keys(errors)[0];
    const matches = [...document.querySelectorAll<HTMLElement>("[data-field]")]
      .filter((element) => element.getAttribute("data-field") === path);
    const target = matches.find((element) => element.matches("input, select, textarea, button")) ?? matches[0];
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "center" });
    target.focus?.();
  }, [errors, message, enabled]);

  const show = (info: PurchasingErrorInfo) => {
    setMessage(info.message);
    setErrors(info.fields);
  };
  const setLocal = (path: string, fieldMessage: string) => {
    setMessage(fieldMessage);
    setErrors({ [path]: fieldMessage });
  };
  const clear = () => {
    setMessage("");
    setErrors({});
  };
  const fieldError = (path: string) => errors[path]
    ? <span role="alert" className="mt-1 block text-xs text-red-700">{errors[path]}</span>
    : null;
  const fieldClass = (path: string) => errors[path] ? "border-red-500 ring-2 ring-red-200" : "";
  return { errors, message, show, setLocal, clear, fieldError, fieldClass };
}
