import { useQuery } from "@tanstack/react-query";
import { useParams } from "react-router-dom";
import api from "@/api/client";
import Loading from "@/components/ui/Loading";
import DocumentPrintTemplate from "@/components/print/DocumentPrintTemplate";

interface PrintPosItem {
  id: number;
  product_code: string;
  product_name: string;
  uom: string;
  quantity: number;
  unit_price: number;
  tax_rate: number;
  tax_amount: number;
}
interface PrintPosSale {
  id: number;
  transaction_number: string;
  status: string;
  sale_date: string;
  warehouse_name?: string | null;
  customer_name?: string | null;
  payment_method: string;
  payment_received: number;
  change_amount: number;
  discount_amount: number;
  subtotal: number;
  tax_amount: number;
  total_amount: number;
  notes?: string | null;
  created_by_name?: string | null;
  printed_by: string;
  generated_at: string;
  items: PrintPosItem[];
}

const num = (value: unknown) => Number(value ?? 0).toLocaleString("id-ID", { maximumFractionDigits: 4 });
const money = (value: unknown) => "Rp " + Number(value ?? 0).toLocaleString("id-ID", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function PosReceiptPrintPage() {
  const { id } = useParams();
  const query = useQuery({ queryKey: ["pos-sale", id, "print"], queryFn: async () => (await api.get<PrintPosSale>(`/pos/${id}/print`)).data, enabled: Boolean(id) });
  if (query.isLoading) return <Loading />;
  if (!query.data) return <p>Document could not be loaded.</p>;
  const data = query.data;
  const paymentLabel: Record<string, string> = { CASH: "Cash", CARD: "Card", BANK_TRANSFER: "Bank Transfer" };
  return <DocumentPrintTemplate
    title="POS Receipt"
    documentNumber={data.transaction_number}
    documentDate={new Date(`${data.sale_date}T00:00:00`).toLocaleDateString("id-ID")}
    status={data.status}
    fields={[
      { label: "WAREHOUSE", value: data.warehouse_name },
      { label: "CUSTOMER", value: data.customer_name },
      { label: "CASHIER", value: data.created_by_name },
      { label: "PAYMENT", value: paymentLabel[data.payment_method] ?? "-" },
      { label: "RECEIVED", value: money(data.payment_received) },
      { label: "CHANGE", value: money(data.change_amount) },
    ]}
    columns={[
      { label: "CODE", align: "left", render: (item: PrintPosItem) => item.product_code },
      { label: "DESCRIPTION", align: "left", render: (item: PrintPosItem) => item.product_name },
      { label: "QTY", align: "right", render: (item: PrintPosItem) => `${num(item.quantity)} ${item.uom}` },
      { label: "PRICE", align: "right", render: (item: PrintPosItem) => money(item.unit_price) },
      { label: "PPN", align: "right", render: (item: PrintPosItem) => money(item.tax_amount) },
      { label: "AMOUNT", align: "right", render: (item: PrintPosItem) => money(Number(item.quantity) * Number(item.unit_price) + Number(item.tax_amount)) },
    ]}
    rows={data.items}
    rowKey={(item) => item.id}
    totals={[
      { label: "Subtotal", value: money(data.subtotal) },
      { label: "Discount", value: data.discount_amount > 0 ? `-${money(data.discount_amount)}` : "-" },
      { label: "PPN", value: money(data.tax_amount) },
      { label: "Total", value: money(data.total_amount), emphasis: true },
    ]}
    notes={data.notes}
    footer={<>Printed by {data.printed_by} · {new Date(data.generated_at).toLocaleString()}</>}
  />;
}