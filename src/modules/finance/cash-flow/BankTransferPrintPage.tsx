import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import Loading from "@/components/ui/Loading";
import DocumentPrintTemplate from "@/components/print/DocumentPrintTemplate";
import { getTransferPrint } from "./api";

const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function BankTransferPrintPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ["bank-transfer", id, "print"], queryFn: () => getTransferPrint(Number(id)), enabled: !!id });
  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>Transfer could not be loaded.</p>;
  const transfer: any = query.data;
  const rows = [{ id: transfer.id, description: `${transfer.source_account_name} → ${transfer.destination_account_name}`, amount: transfer.amount }];
  return <DocumentPrintTemplate
    title="Bank Transfer"
    documentNumber={transfer.transfer_number}
    documentDate={transfer.transfer_date ? new Date(transfer.transfer_date).toLocaleDateString() : "—"}
    status={transfer.status}
    fields={[
      { label: "SOURCE", value: `${transfer.source_account_name}` },
      { label: "DESTINATION", value: `${transfer.destination_account_name}` },
      { label: "CURRENCY", value: transfer.currency },
      { label: "REFERENCE", value: transfer.reference_number },
      { label: "JOURNAL", value: transfer.journal_number },
    ]}
    columns={[
      { label: "DESCRIPTION", align: "left", render: (row: any) => row.description },
      { label: "AMOUNT", align: "right", render: (row: any) => money(row.amount) },
    ]}
    rows={rows}
    rowKey={(row: any) => row.id}
    totals={[{ label: "TOTAL", value: `${money(transfer.amount)} ${transfer.currency}`, emphasis: true }]}
    notes={transfer.notes}
    signatures={[
      { label: "Prepared By", name: transfer.created_by_name, signedAt: transfer.created_at },
      ...(transfer.posted_by_name ? [{ label: "Posted By", name: transfer.posted_by_name, signedAt: transfer.posted_at, status: transfer.status }] : []),
    ]}
    authenticity={[
      { label: "CREATOR", value: transfer.created_by_name },
      { label: "CREATED AT", value: transfer.created_at ? new Date(transfer.created_at).toLocaleString("id-ID") : undefined },
      { label: "POSTED BY", value: transfer.posted_by_name },
      { label: "POSTED AT", value: transfer.posted_at ? new Date(transfer.posted_at).toLocaleString("id-ID") : undefined },
      { label: "PRINTED BY", value: transfer.printed_by },
      { label: "PRINTED AT", value: transfer.generated_at ? new Date(transfer.generated_at).toLocaleString("id-ID") : undefined },
      { label: "DOCUMENT #", value: transfer.transfer_number },
      { label: "STATUS", value: transfer.status },
    ]}
    footer={<>System document · {transfer.transfer_number} · Printed by {transfer.printed_by || "—"}</>}
  />;
}
