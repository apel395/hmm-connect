import type { PrintSignature } from "./DocumentPrintTemplate";

export interface PrintApprovalRecord {
  level?: number;
  name?: string | null;
  status?: string | null;
  approver_name?: string | null;
  decided_at?: string | null;
  signature_name?: string | null;
  signature_label?: string | null;
  signature_image?: string | null;
}

const personName = (name?: string | null) => (name ?? "").normalize("NFKC").trim().replace(/\s+/g, " ").toLowerCase();

export function approvalSignature(record: PrintApprovalRecord): PrintSignature {
  const actualName = record.approver_name?.trim();
  const approved = record.status?.toUpperCase() === "APPROVED";
  const matchingOwner = Boolean(approved && actualName && record.decided_at &&
    personName(actualName) === personName(record.signature_name));
  return {
    label: record.name || `Approval Level ${record.level ?? "—"}`,
    name: actualName || "—",
    imageSrc: matchingOwner ? record.signature_image || undefined : undefined,
    signedAt: record.decided_at,
    status: record.status,
  };
}

export function approvalPrintSignatures(records?: PrintApprovalRecord[] | null): PrintSignature[] {
  return (records ?? []).filter(record => record.status?.toUpperCase() === "APPROVED").map(approvalSignature);
}
