import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import api from "@/api/client";
import Loading from "@/components/ui/Loading";
import DocumentPrintTemplate from "@/components/print/DocumentPrintTemplate";

const qty = (value: unknown) => Number(value || 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });

export default function StockOpnamePrintPage() {
  const { id } = useParams();
  const query = useQuery({
    queryKey: ["stock-opname", id, "print"],
    queryFn: async () => (await api.get(`/stock-opnames/${id}/print`)).data,
    enabled: Boolean(id),
  });

  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>Stock Opname could not be loaded.</p>;
  const data: any = query.data;
  const approvals = (data.approval_history ?? [])
    .filter((step: any) => step.status === "APPROVED")
    .map((step: any) => ({
      label: step.signature_label || step.name || ("Approval Level " + step.level),
      name: step.signature_name || step.approver_name || "Approved",
      imageSrc: step.signature_image || undefined,
      signedAt: step.decided_at,
      status: step.status,
    }));

  return <DocumentPrintTemplate
    title="Stock Opname Count Sheet"
    documentNumber={data.opname_number}
    documentDate={data.count_date}
    status={data.status}
    fields={[
      { label: "WAREHOUSE", value: data.warehouse_name },
      { label: "LOCATION", value: data.location_name },
      { label: "BUSINESS UNIT", value: data.business_unit_name },
      { label: "DEPARTMENT", value: data.department_name },
    ]}
    columns={[
      { label: "NO", align: "center", render: (_row: any, index: number) => index + 1 },
      { label: "CODE", align: "left", render: (row: any) => row.product_code },
      { label: "DESCRIPTION", align: "left", render: (row: any) => row.product_name },
      { label: "UOM", align: "center", render: (row: any) => row.uom || "—" },
      ...(!data.blind_count ? [{ label: "SYSTEM QTY", align: "right" as const, render: (row: any) => qty(row.system_quantity) }] : []),
      { label: "PHYSICAL COUNT", align: "center", render: () => <span className="inline-block min-w-24 border-b border-black">&nbsp;</span> },
    ]}
    rows={data.items ?? []}
    rowKey={(row: any) => row.id}
    notes={data.notes || "Physical quantity is written by the counting team on this sheet, then entered into MMH-Connect."}
    signatures={approvals}
    footer={<>Field count sheet · {data.opname_number}</>}
  />;
}
