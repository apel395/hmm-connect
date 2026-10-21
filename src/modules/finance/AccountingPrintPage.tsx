import { approvalPrintSignatures } from "@/components/print/approvalSignatures";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import api from "@/api/client";
import Loading from "@/components/ui/Loading";
import DocumentPrintTemplate from "@/components/print/DocumentPrintTemplate";

const money = (value: unknown) => Number(value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const date = (value: unknown) => value ? new Date(String(value)).toLocaleDateString() : "—";

export default function AccountingPrintPage({ kind }: { kind: "supplier-invoices" | "journal-entries" | "payments" }) {
  const { id } = useParams();
  const query = useQuery({ queryKey: [kind, id, "print"], queryFn: async () => (await api.get(`/${kind}/${id}/print`)).data, enabled: !!id });
  if (query.isLoading) return <Loading/>;
  if (!query.data) return <p>Document could not be loaded.</p>;
  const data = query.data as any;
  const isJournal = kind === "journal-entries";
  const isPayment = kind === "payments";
  const rows: any[] = isPayment ? (data.allocations ?? []) : (data.lines ?? []);
  const title = isPayment ? "Payment" : isJournal ? "Journal Entry" : "Supplier Invoice";
  const documentNumber = data.payment_number || data.journal_number || data.internal_invoice_number;
  const documentDate = data.payment_date || data.journal_date || data.posting_date || data.invoice_date;

  const fields = isPayment ? [
    { label: "PAY TO", value: data.supplier_name },
    { label: "PAYMENT METHOD", value: String(data.payment_method || "—").replaceAll("_", " ") },
    { label: "REFERENCE", value: data.reference_number },
    { label: "UNIT BISNIS", value: data.business_unit_name ?? (data.business_unit_id ? `#${data.business_unit_id}` : undefined) },
    { label: "LOCATION", value: data.location_name ?? (data.location_id ? `#${data.location_id}` : undefined) },
    { label: "DEPARTMENT", value: data.department_name ?? (data.department_id ? `#${data.department_id}` : undefined) },
  ] : isJournal ? [
    { label: "REFERENCE", value: data.reference_number || data.document_number },
    { label: "DESCRIPTION", value: data.description },
    { label: "UNIT BISNIS", value: data.business_unit_name ?? (data.business_unit_id ? `#${data.business_unit_id}` : undefined) },
    { label: "LOCATION", value: data.location_name ?? (data.location_id ? `#${data.location_id}` : undefined) },
    { label: "DEPARTMENT", value: data.department_name ?? (data.department_id ? `#${data.department_id}` : undefined) },
  ] : [
    { label: "SUPPLIER", value: data.supplier_name },
    { label: "SUPPLIER INVOICE #", value: data.supplier_invoice_number },
    { label: "PO #", value: data.purchase_order_number },
    { label: "RECEIVING #", value: data.receipt_number },
    { label: "UNIT BISNIS", value: data.business_unit_name ?? (data.business_unit_id ? `#${data.business_unit_id}` : undefined) },
    { label: "LOCATION", value: data.location_name ?? (data.location_id ? `#${data.location_id}` : undefined) },
    { label: "DEPARTMENT", value: data.department_name ?? (data.department_id ? `#${data.department_id}` : undefined) },
    { label: "DUE DATE", value: data.due_date ? date(data.due_date) : undefined },
  ];

  const columns = isJournal ? [
    { label: "ACCOUNT", align: "left" as const, render: (line: any) => line.account_name || "—" },
    { label: "DESCRIPTION", align: "left" as const, render: (line: any) => line.description || "—" },
    { label: "DEBIT", align: "right" as const, render: (line: any) => money(line.debit) },
    { label: "CREDIT", align: "right" as const, render: (line: any) => money(line.credit) },
  ] : isPayment ? [
    { label: "INVOICE", align: "left" as const, render: (line: any) => line.invoice_number || line.internal_invoice_number || "—" },
    { label: "DUE DATE", align: "center" as const, render: (line: any) => line.due_date ? date(line.due_date) : "—" },
    { label: "INVOICE TOTAL", align: "right" as const, render: (line: any) => money(line.invoice_total) },
    { label: "AMOUNT", align: "right" as const, render: (line: any) => money(line.allocated_amount) },
  ] : [
    {
      label: "ITEM",
      align: "left" as const,
      render: (line: any) => {
        const item = String(line.product_name || line.description || "Manual line").trim();
        const description = String(line.description || "").trim();
        const showDescription = Boolean(
          description &&
          description.localeCompare(item, undefined, { sensitivity: "accent" }) !== 0,
        );
        return (
          <>
            <div>{item}</div>
            {showDescription ? <div className="mt-0.5 text-[10px] text-slate-500">{description}</div> : null}
          </>
        );
      },
    },
    { label: "QTY", align: "right" as const, render: (line: any) => line.quantity },
    { label: "UOM", align: "center" as const, render: (line: any) => line.uom || "—" },
    { label: "UNIT PRICE", align: "right" as const, render: (line: any) => money(line.unit_price) },
    ...(rows.some((line: any) => Number(line.tax_amount || 0) !== 0 || Number(line.tax_rate || 0) !== 0)
      ? [{ label: "PPN", align: "right" as const, render: (line: any) => money(line.tax_amount) }]
      : []),
    { label: "ACCOUNT", align: "left" as const, render: (line: any) => line.account_name || "—" },
    { label: "LINE TOTAL", align: "right" as const, render: (line: any) => money(line.line_amount) },
  ];

  const totals = isJournal ? [
    { label: "TOTAL DEBIT", value: money(data.total_debit), emphasis: true },
    { label: "TOTAL CREDIT", value: money(data.total_credit), emphasis: true },
  ] : isPayment ? [
    { label: "INVOICE SETTLEMENT", value: money(data.total_amount) },
    ...(Number(data.bank_charge_amount || 0) ? [{ label: "BANK CHARGE", value: money(data.bank_charge_amount) }] : []),
    ...(Number(data.short_over_amount || 0) ? [{ label: "SHORT / OVER", value: money(data.short_over_amount) }] : []),
    { label: "TOTAL FUNDED", value: money(data.funded_amount), emphasis: true },
  ] : [
    { label: "SUBTOTAL", value: money(data.subtotal) },
    ...(Number(data.discount_amount || 0) ? [{ label: "DISCOUNT", value: money(-Number(data.discount_amount)) }] : []),
    ...(Number(data.tax_amount || 0) ? [{ label: "VAT / TAX", value: money(data.tax_amount) }] : []),
    ...(Number(data.withholding_tax_amount || 0) ? [{ label: "WITHHOLDING TAX", value: money(-Number(data.withholding_tax_amount)) }] : []),
    { label: "TOTAL", value: money(data.total_amount), emphasis: true },
  ];

  const approvalSignatures = approvalPrintSignatures(data.approval_history);
  if (!approvalSignatures.length && data.approved_by_name) approvalSignatures.push({ label: "Approved By", name: data.approved_by_name, signedAt: data.approved_at || null, status: "APPROVED" });
  const creator = data.created_by_name || data.requester_name || data.received_by_name;

  const funding = isPayment && data.funding_lines?.length ? <section className="avoid-break mt-6"><div className="mb-2 font-semibold">FUNDING ACCOUNTS</div><table className="w-full border-collapse text-[11px]"><thead><tr><th className="border-y border-black px-2 py-1 text-left">BANK</th><th className="border-y border-black px-2 py-1 text-left">ACCOUNT</th><th className="border-y border-black px-2 py-1 text-left">ACCOUNT NUMBER</th><th className="border-y border-black px-2 py-1 text-right">AMOUNT</th></tr></thead><tbody>{data.funding_lines.map((line: any) => <tr key={line.id}><td className="border-b px-2 py-1">{line.bank_name}</td><td className="border-b px-2 py-1">{line.account_name}</td><td className="border-b px-2 py-1">{line.account_number}</td><td className="border-b px-2 py-1 text-right">{money(line.amount)}</td></tr>)}</tbody></table></section> : undefined;

  return <DocumentPrintTemplate
    title={title}
    documentNumber={documentNumber}
    documentDate={date(documentDate)}
    status={data.status}
    fields={fields}
    columns={columns}
    rows={rows}
    rowKey={(row: any, index) => row.id ?? index}
    totals={totals}
    notes={data.notes || data.description}
    extraAfterTable={funding}
    signatures={approvalSignatures.length ? approvalSignatures : isPayment ? [
      { label: "Prepared By", name: data.created_by_name || "Finance", signedAt: data.created_at },
      { label: "Receiver / Bank Reference", name: data.reference_number },
    ] : [
      { label: "Prepared By", name: data.created_by_name, signedAt: data.created_at },
      { label: "Posted By", name: data.posted_by_name, signedAt: data.posted_at },
    ]}
    authenticity={[
      { label: "CREATOR", value: creator },
      { label: "CREATED AT", value: data.created_at ? new Date(data.created_at).toLocaleString("id-ID") : undefined },
      { label: "POSTED BY", value: data.posted_by_name },
      { label: "POSTED AT", value: data.posted_at ? new Date(data.posted_at).toLocaleString("id-ID") : undefined },
      { label: "PRINTED BY", value: data.printed_by || data.generated_by_name || "Finance" },
      { label: "PRINTED AT", value: data.generated_at ? new Date(data.generated_at).toLocaleString("id-ID") : undefined },
      { label: "DOCUMENT #", value: documentNumber },
      { label: "STATUS", value: data.status },
    ]}
    footer={<>System document · {documentNumber || "—"} · Created by {creator || "—"} · Printed {data.generated_at ? new Date(data.generated_at).toLocaleString("id-ID") : "—"}</>}
  />;
}
