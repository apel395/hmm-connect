type ApiError = {
  message?: string;
  response?: { data?: { detail?: unknown } };
};

/** Read a backend error detail without assuming the thrown value's shape. */
export function warehouseErrorMessage(error: unknown, fallback = "Action failed"): string {
  const candidate = error as ApiError | null | undefined;
  const detail = candidate?.response?.data?.detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  return candidate?.message || fallback;
}
