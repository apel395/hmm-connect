import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import Loading from "@/components/ui/Loading";
import DocumentPrintTemplate from "@/components/print/DocumentPrintTemplate";
import { getTransfer } from "./api";

const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function BankTransferPrintPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ["bank-transfer", id, "print"], queryFn: () => getTransfer(Number(id)), enabled: !!id });
  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>Transfer could not be loaded.</p>;
  const transfer: any = query.data;
  const rows = [{ id: transfer.id, description: `${transfer.source_account_code} — ${transfer.source_account_name} → ${transfer.destination_account_code} — ${transfer.destination_account_name}`, amount: transfer.amount }];
  return <DocumentPrintTemplate
    title="Bank Transfer"
    documentNumber={transfer.transfer_number}
    documentDate={transfer.transfer_date ? new Date(transfer.transfer_date).toLocaleDateString() : "—"}
    status={transfer.status}
    fields={[
      { label: "SOURCE", value: `${transfer.source_account_code} — ${transfer.source_account_name}` },
      { label: "DESTINATION", value: `${transfer.destination_account_code} — ${transfer.destination_account_name}` },
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
    signatures={[{ label: "Prepared By" }, { label: "Checked By" }, { label: "Approved By" }]}
  />;
}
