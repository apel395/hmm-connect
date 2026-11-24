/**
 * Shared frontend contracts for finance modules.
 *
 * These types mirror backend response shapes that several modules rely on.
 * They intentionally stay frontend-only: no permission, posting, allocation,
 * or validation rule is implemented here.
 */

export type FinancePage<T> = {
  items: T[];
  page: number;
  page_size: number;
  total_items: number;
  total_pages: number;
  has_next: boolean;
  has_previous: boolean;
};

export type FinancePageParams = {
  page?: number;
  pageSize?: number;
  page_size?: number;
  search?: string;
  status?: string;
  [key: string]: unknown;
};

/** Normalize the frontend `pageSize` name to the backend `page_size` name. */
export const financePageParams = ({
  page = 1,
  pageSize,
  page_size,
  search,
  ...rest
}: FinancePageParams = {}) => ({
  page,
  page_size: pageSize ?? page_size ?? 50,
  search: search?.trim() || undefined,
  ...rest,
});

export type PaymentStatus = "PAID" | "PARTIALLY_PAID" | "UNPAID";

export type AgingBucket = "current" | "1_30" | "31_60" | "61_90" | "over_90";

/** Backend can still emit raw `PARTIAL`; reporting always shows `PARTIALLY_PAID`. */
export type RawPaymentStatus = PaymentStatus | "PARTIAL";

export const REPORTED_PAYMENT_STATUS = {
  PAID: "PAID",
  PARTIAL: "PARTIALLY_PAID",
  PARTIALLY_PAID: "PARTIALLY_PAID",
  UNPAID: "UNPAID",
} as const;

export type ReportedPaymentStatus =
  (typeof REPORTED_PAYMENT_STATUS)[keyof typeof REPORTED_PAYMENT_STATUS];

export function reportedPaymentStatus(
  status: string | null | undefined,
): ReportedPaymentStatus {
  if (!status) return "UNPAID";
  const key = status.toUpperCase();
  if (key in REPORTED_PAYMENT_STATUS) {
    return REPORTED_PAYMENT_STATUS[key as keyof typeof REPORTED_PAYMENT_STATUS];
  }
  if (key === "UNPAID" || key === "PAID") return key;
  return "UNPAID";
}

/**
 * Capabilities returned by backend detail endpoints. Absent means the UI must
 * not offer the action; it never means "allowed".
 */
export type FinanceAllowedActions = {
  can_submit?: boolean;
  can_approve?: boolean;
  can_reject?: boolean;
  can_void?: boolean;
  can_print?: boolean;
  can_edit?: boolean;
  can_delete?: boolean;
  can_verify?: boolean;
  can_generate_journal?: boolean;
  can_manage?: boolean;
  can_post?: boolean;
  can_unpost?: boolean;
  can_reopen?: boolean;
  can_cancel_posted?: boolean;
  [action: string]: boolean | undefined;
};

export type FinanceActivityEvent = {
  id: number;
  action: string;
  summary: string;
  actor_name?: string | null;
  occurred_at: string;
};

export type FinanceFieldIssue = {
  path: string;
  message: string;
  actual?: string;
  expected?: string;
};
