import type { BadgeVariant } from "@/components/ui/Badge";

const statusLabels: Record<string, string> = {
  DRAFT: "Draft",
  PENDING: "Waiting Approval",
  SUBMITTED: "Submitted",
  PENDING_APPROVAL: "Waiting Approval",
  APPROVED: "Approved",
  REJECTED: "Rejected",
  CANCELLED: "Cancelled",
  CONVERTED: "Converted",
  PARTIALLY_RECEIVED: "Partially Received",
  RECEIVED: "Received",
  RETURNED: "Returned",
  POSTED: "Posted",
  VOID: "Void",
  IN_REVIEW: "In Review",
  REVIEW_REQUIRED: "Tax Review Required",
};

const statusVariants: Record<string, BadgeVariant> = {
  DRAFT: "outline",
  PENDING: "warning",
  SUBMITTED: "warning",
  PENDING_APPROVAL: "warning",
  APPROVED: "success",
  REJECTED: "danger",
  CANCELLED: "secondary",
  CONVERTED: "info",
  PARTIALLY_RECEIVED: "primary",
  RECEIVED: "info",
  RETURNED: "warning",
  POSTED: "success",
  VOID: "secondary",
  IN_REVIEW: "warning",
  REVIEW_REQUIRED: "warning",
};

export function purchasingStatusLabel(value?: string | null) {
  if (!value) return "—";
  const key = String(value).toUpperCase();
  if (statusLabels[key]) return statusLabels[key];
  return String(value)
    .replace(/[_-]+/g, " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

export function purchasingStatusVariant(value?: string | null): BadgeVariant {
  if (!value) return "outline";
  return statusVariants[String(value).toUpperCase()] ?? "outline";
}
