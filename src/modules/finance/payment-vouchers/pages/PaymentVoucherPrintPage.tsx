import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import { getVoucherPrint } from "../api";
import useAuthStore from "@/store/auth";
import DocumentPrintTemplate from "@/components/print/DocumentPrintTemplate";

const money = (v: unknown) => Number(v || 0).toLocaleString("id-ID", { minimumFractionDigits: 2 });

export default function PaymentVoucherPrintPage() {
  const { id } = useParams();
  const voucherId = Number(id);
  const user = useAuthStore((s) => s.user);
  const q = useQuery({ queryKey: ["payment-voucher-print", voucherId], queryFn: async () => (await getVoucherPrint(voucherId)).data });

  if (q.isLoading) return <div className="py-16 text-center">Loading print...</div>;
  if (q.isError) return <div className="py-16 text-center text-red-600">Failed to load.</div>;
  const v: any = q.data;

  const rows = (v.groups ?? []).map((g: any, idx: number) => ({ ...g, row_number: idx + 1 }));
  const approvalSignatures = (v.approval_history ?? []).filter((step: any) => step.status === "APPROVED").map((step: any) => ({
    label: step.signature_label || step.name || ("Approval Level " + step.level),
    name: step.signature_name || step.approver_name || "Approved",
    imageSrc: step.signature_image || undefined,
    signedAt: step.decided_at,
    status: step.status,
  }));
  if (!approvalSignatures.length && v.approved_by_name) approvalSignatures.push({ label: "Approved By", name: v.approved_by_name, signedAt: v.approved_at, status: "APPROVED" });

  return <DocumentPrintTemplate
    title="Payment Voucher"
    documentNumber={v.voucher_number}
    documentDate={v.voucher_date}
    status={v.status}
    fields={[
      { label: "LOCATION", value: v.location_name },
      { label: "BUSINESS UNIT", value: v.business_unit_name },
      { label: "DEPARTMENT", value: v.department_name },
      { label: "PERIOD", value: (v.period_from || "—") + " — " + (v.period_to || "—") },
      { label: "CREATED BY", value: v.created_by_name },
    ]}
    columns={[
      { label: "NO", align: "center", render: (row: any) => row.row_number },
      { label: "SUPPLIER", align: "left", render: (row: any) => row.supplier_name },
      { label: "BANK", align: "left", render: (row: any) => row.bank?.bank_name || "—" },
      { label: "ACCOUNT NUMBER", align: "left", render: (row: any) => row.bank?.account_number || "—" },
      { label: "ACCOUNT NAME", align: "left", render: (row: any) => row.bank?.account_name || row.supplier_name },
      { label: "AMOUNT", align: "right", render: (row: any) => money(row.total) },
    ]}
    rows={rows}
    rowKey={(row: any) => row.supplier_id}
    totals={[{ label: "TOTAL", value: money(v.total_amount), emphasis: true }]}
    notes={v.notes}
    signatures={approvalSignatures.length ? approvalSignatures : [{ label: "Prepared By", name: v.created_by_name, signedAt: v.created_at }]}
    authenticity={[
      { label: "CREATOR", value: v.created_by_name },
      { label: "CREATED AT", value: v.created_at ? new Date(v.created_at).toLocaleString("id-ID") : undefined },
      { label: "APPROVED BY", value: v.approved_by_name },
      { label: "APPROVED AT", value: v.approved_at ? new Date(v.approved_at).toLocaleString("id-ID") : undefined },
      { label: "PRINTED BY", value: v.printed_by || user?.full_name || user?.username },
      { label: "PRINTED AT", value: v.generated_at ? new Date(v.generated_at).toLocaleString("id-ID") : new Date().toLocaleString("id-ID") },
      { label: "DOCUMENT #", value: v.voucher_number },
      { label: "STATUS", value: v.status },
    ]}
    footer={<>System document · {v.voucher_number} · {v.groups?.length || 0} supplier(s) · {v.allocations?.length || 0} invoice(s)</>}
  />;
}
