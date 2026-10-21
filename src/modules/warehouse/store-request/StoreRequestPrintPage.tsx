import { approvalPrintSignatures } from "@/components/print/approvalSignatures";
import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import api from "@/api/client";
import Loading from "@/components/ui/Loading";
import DocumentPrintTemplate, { type PrintSignature } from "@/components/print/DocumentPrintTemplate";
import type { StoreRequestItem } from "./types";

interface PrintApproval {
  level: number;
  name: string;
  status: string;
  approver_name?: string | null;
  decided_at?: string | null;
  signature_name?: string | null;
  signature_label?: string | null;
  signature_image?: string | null;
}
interface PrintStoreRequest {
  sr_number: string;
  status: string;
  request_date: string;
  requester_name?: string | null;
  business_unit_name?: string | null;
  department_name?: string | null;
  location_name?: string | null;
  warehouse_name?: string | null;
  notes?: string | null;
  created_by_name?: string | null;
  created_at?: string | null;
  printed_by: string;
  generated_at: string;
  items: StoreRequestItem[];
  approval_history?: PrintApproval[];
}

const number = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });

export default function StoreRequestPrintPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ["store-request", id, "print"], queryFn: async () => (await api.get<PrintStoreRequest>(`/store-requests/${id}/print`)).data, enabled: Boolean(id) });
  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>Document could not be loaded.</p>;
  const data = query.data;
  const signatures: PrintSignature[] = [
    { label: "Created by", name: data.created_by_name || data.requester_name || "—", signedAt: data.created_at },
    ...approvalPrintSignatures(data.approval_history),
  ];
  return <DocumentPrintTemplate
    title="Store Request"
    documentNumber={data.sr_number}
    documentDate={new Date(`${data.request_date}T00:00:00`).toLocaleDateString("id-ID")}
    status={data.status}
    fields={[
      { label: "REQUESTER", value: data.requester_name },
      { label: "UNIT BISNIS", value: data.business_unit_name },
      { label: "LOCATION", value: data.location_name },
      { label: "DEPARTMENT", value: data.department_name },
      { label: "WAREHOUSE", value: data.warehouse_name },
    ]}
    columns={[
      { label: "CODE", align: "left", render: (item: StoreRequestItem) => item.product_code },
      { label: "DESCRIPTION", align: "left", render: (item: StoreRequestItem) => item.product_name },
      { label: "REQUESTED", align: "right", render: (item: StoreRequestItem) => number(item.requested_quantity) },
      { label: "ISSUED", align: "right", render: (item: StoreRequestItem) => number(item.issued_quantity) },
      { label: "REMAINING", align: "right", render: (item: StoreRequestItem) => number(item.remaining_quantity) },
      { label: "UOM", align: "center", render: (item: StoreRequestItem) => item.uom },
    ]}
    rows={data.items}
    rowKey={(item) => item.id}
    notes={data.notes}
    signatures={signatures}
    footer={<>Printed by {data.printed_by} · {new Date(data.generated_at).toLocaleString()}</>}
  />;
}
