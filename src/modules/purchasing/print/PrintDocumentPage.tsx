import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import api from "@/api/client";
import Loading from "@/components/ui/Loading";
import DocumentPrintTemplate, { type PrintSignature } from "@/components/print/DocumentPrintTemplate";
import {
  MMHPurchaseOrderPrint,
  MMHPurchaseRequisitionPrint,
  type MMHPrintItem,
  type MMHPrintSignature,
  type MMHProcurementPrintData,
} from "@/components/print/MMHProcurementPrintTemplates";

interface PrintItem extends MMHPrintItem {
  product_code?: string;
  product_name: string;
  uom?: string;
  quantity: number;
  unit_price?: number;
  estimated_price?: number;
  unit_cost?: number;
  total_price?: number;
  line_total?: number;
}

interface ApprovalRecord {
  level: number;
  name: string;
  status: string;
  approver_name?: string | null;
  approver_role?: string | null;
  decided_at?: string | null;
  comment?: string | null;
  signature_name?: string | null;
  signature_label?: string | null;
  signature_image?: string | null;
}

interface PrintDocument {
  document_type: string;
  brand_name?: string;
  hotel_name?: string;
  pr_number?: string;
  ml_number?: string;
  po_number?: string;
  receipt_number?: string;
  request_date?: string;
  order_date?: string;
  received_at?: string;
  expected_date?: string;
  expiry_date?: string;
  supplier_name?: string;
  requester_name?: string;
  status?: string;
  destination_type?: string;
  warehouse_name?: string | null;
  delivery_note_number?: string | null;
  external_reference?: string | null;
  business_unit_name?: string | null;
  department_name?: string | null;
  location_name?: string | null;
  business_unit_id?: number | null;
  department_id?: number | null;
  location_id?: number | null;
  notes?: string | null;
  subtotal?: number;
  discount_amount?: number;
  tax_amount?: number;
  total_amount?: number;
  total_value?: number;
  printed_by: string;
  generated_at: string;
  items: PrintItem[];
  approval_history?: ApprovalRecord[];
  source_pr_number?: string | null;
  purchase_order_number?: string | null;
}

const money = (value: unknown) => Number(value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const displayDate = (value?: string) => value ? new Date(value).toLocaleDateString() : "—";
const longDate = (value?: string) => value ? new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString("id-ID", { day: "numeric", month: "long", year: "numeric" }) : "—";

function approvedSignatures(data: PrintDocument): PrintSignature[] {
  const approved = (data.approval_history ?? []).filter((record) => record.status === "APPROVED");
  return approved.map((record) => ({
    label: record.signature_label || record.approver_role || record.name || `Approval Level ${record.level}`,
    name: record.signature_name || record.approver_name || record.status,
    imageSrc: record.signature_image || undefined,
  }));
}

function mmhPrSignatures(data: PrintDocument): MMHPrintSignature[] {
  const approved = approvedSignatures(data);
  const signatures: MMHPrintSignature[] = [{ label: "Prepared by", name: data.requester_name }];
  const fallbackLabels = ["Submitted by", "Checked by", "Approved by"];
  approved.slice(0, 3).forEach((signature, index) => signatures.push({ ...signature, label: signature.label || fallbackLabels[index] }));
  while (signatures.length < 4) signatures.push({ label: fallbackLabels[signatures.length - 1] });
  return signatures.slice(0, 4);
}

function mmhPoSignatures(data: PrintDocument): MMHPrintSignature[] {
  const approved = approvedSignatures(data);
  const labels = ["Dibuat oleh", "Diverifikasi oleh", "Diketahui oleh"];
  const signatures: MMHPrintSignature[] = [{ label: labels[0], name: data.printed_by }];
  approved.slice(0, 2).forEach((signature, index) => signatures.push({ ...signature, label: signature.label || labels[index + 1] }));
  while (signatures.length < 3) signatures.push({ label: labels[signatures.length] });
  return signatures;
}

function procurementPrintData(data: PrintDocument, isPr: boolean, isPo: boolean): MMHProcurementPrintData {
  const itemSubtotal = data.items.reduce((sum, item) => sum + Number(item.total_price ?? Number(item.quantity) * Number(item.unit_price ?? item.estimated_price ?? 0)), 0);
  const subtotal = Number(data.subtotal ?? itemSubtotal);
  const taxAmount = Number(data.tax_amount ?? data.items.reduce((sum, item) => sum + Number(item.tax_amount ?? 0), 0));
  const totalAmount = Number(data.total_amount ?? subtotal + taxAmount);

  return {
    documentNumber: isPr ? data.pr_number : data.po_number,
    documentDate: longDate(isPr ? data.request_date : data.order_date),
    requesterName: data.requester_name,
    supplierName: data.supplier_name,
    locationName: data.location_name ?? undefined,
    businessUnitName: data.business_unit_name ?? undefined,
    departmentName: data.department_name ?? undefined,
    deliveryDate: longDate(data.expected_date),
    attn: data.supplier_name,
    contact: undefined,
    purpose: undefined,
    eventOperation: undefined,
    revision: undefined,
    notes: data.notes,
    subtotal,
    discountAmount: data.discount_amount,
    taxAmount,
    totalAmount,
    items: data.items,
    signatures: isPr ? mmhPrSignatures(data) : mmhPoSignatures(data),
  };
}

export default function PrintDocumentPage({ kind }: { kind: "purchase-requisitions" | "market-lists" | "purchase-orders" | "goods-receipts" }) {
  const { id } = useParams();
  const query = useQuery({ queryKey: [kind, id, "print"], queryFn: async () => (await api.get<PrintDocument>(`/${kind}/${id}/print`)).data, enabled: Boolean(id) });
  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>Document could not be loaded.</p>;

  const data = query.data;
  const isReceipt = kind === "goods-receipts";
  const isPr = kind === "purchase-requisitions";
  const isMl = kind === "market-lists";
  const isPo = kind === "purchase-orders";

  if (isPr) return <MMHPurchaseRequisitionPrint data={procurementPrintData(data, true, false)} />;
  if (isPo) return <MMHPurchaseOrderPrint data={procurementPrintData(data, false, true)} />;

  const number = data.ml_number ?? data.receipt_number;
  const date = data.request_date ?? data.received_at;
  const total = isReceipt
    ? (data.total_value ?? data.items.reduce((sum, item) => sum + Number(item.line_total ?? Number(item.quantity) * Number(item.unit_cost ?? 0)), 0))
    : (data.total_amount ?? data.items.reduce((sum, item) => sum + Number(item.total_price ?? Number(item.quantity) * Number(item.unit_price ?? item.estimated_price ?? 0)), 0));
  const fields = [
    ...((isMl) ? [{ label: "REQUESTER", value: data.requester_name }] : [{ label: "SUPPLIER", value: data.supplier_name }]),
    ...(!isMl && data.source_pr_number ? [{ label: "PR #", value: data.source_pr_number }] : []),
    ...(isReceipt ? [{ label: "PO #", value: data.purchase_order_number ?? data.po_number }, { label: "DELIVERY NOTE", value: data.delivery_note_number ?? data.external_reference }, { label: "DESTINATION", value: data.destination_type === "WAREHOUSE" ? `Warehouse — ${data.warehouse_name ?? ""}` : "Direct Use" }] : []),
    { label: "UNIT BISNIS", value: data.business_unit_name ?? (data.business_unit_id ? `#${data.business_unit_id}` : undefined) },
    { label: "LOCATION", value: data.location_name ?? (data.location_id ? `#${data.location_id}` : undefined) },
    { label: "DEPARTMENT", value: data.department_name ?? (data.department_id ? `#${data.department_id}` : undefined) },
    ...(data.expected_date ? [{ label: "DELIVERY DATE", value: displayDate(data.expected_date) }] : []),
    ...(data.expiry_date ? [{ label: "VALID UNTIL", value: displayDate(data.expiry_date) }] : []),
  ];
  const columns = [
    { label: "CODE", align: "left" as const, render: (item: PrintItem) => <span className="whitespace-nowrap">{item.product_code ?? "—"}</span> },
    { label: "DESCRIPTION", align: "left" as const, render: (item: PrintItem) => <span>{item.product_name}</span> },
    { label: "QTY", align: "right" as const, render: (item: PrintItem) => <span className="whitespace-nowrap">{item.quantity}</span> },
    { label: "UOM", align: "center" as const, render: (item: PrintItem) => <span className="whitespace-nowrap">{item.uom ?? "—"}</span> },
    { label: "PRICE", align: "right" as const, render: (item: PrintItem) => <span className="whitespace-nowrap">{money(isReceipt ? item.unit_cost : item.unit_price ?? item.estimated_price ?? 0)}</span> },
    { label: "AMOUNT", align: "right" as const, render: (item: PrintItem) => <span className="whitespace-nowrap">{money(isReceipt ? (item.line_total ?? Number(item.quantity) * Number(item.unit_cost ?? 0)) : (item.total_price ?? Number(item.quantity) * Number(item.unit_price ?? item.estimated_price ?? 0)))}</span> },
  ];
  const signatures = approvedSignatures(data);
  return <DocumentPrintTemplate title={isReceipt ? "Receiving Report" : data.document_type} documentNumber={number} documentDate={displayDate(date)} status={data.status} fields={fields} columns={columns} rows={data.items} rowKey={(item) => item.id} totals={[{ label: "TOTAL", value: money(total), emphasis: true }]} notes={data.notes} signatures={signatures.length ? signatures : [{ label: "Prepared By", name: data.printed_by }, { label: "Checked By" }, { label: "Approved By" }]} footer={<>Printed by {data.printed_by} · {new Date(data.generated_at).toLocaleString()}</>} />;
}
