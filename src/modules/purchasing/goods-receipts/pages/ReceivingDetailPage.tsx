import { ArrowLeft, Printer } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";
import { useGoodsReceipt, usePostGoodsReceipt } from "../hooks/useGoodsReceipts";
import DocumentActivity from "../../components/DocumentActivity";
import useAuthorization from "@/hooks/useAuthorization";

export default function ReceivingDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { data, isLoading } = useGoodsReceipt(Number(id));
  const post = usePostGoodsReceipt();
  const { canPerform } = useAuthorization();
  if (isLoading) return <Loading/>;
  if (!data) return null;
  const actions = data.allowed_actions;
  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-4"><div className="flex items-center gap-4"><Button variant="outline" size="sm" onClick={() => navigate("/receiving")}><ArrowLeft size={17}/> Back</Button><div><div className="text-sm text-slate-500">Receiving</div><div className="flex items-center gap-3"><h1 className="text-2xl font-bold">{data.receipt_number}</h1><Badge>{data.status}</Badge></div></div></div>
      <div className="flex gap-2">{actions?.can_print !== false && <Button variant="outline" aria-label="Print receiving document" title="Print" onClick={() => window.open(`/receiving/${data.id}/print`, "_blank")}><Printer size={18}/></Button>}{canPerform("post", ["WAREHOUSE"], actions?.can_post ?? false) && <Button loading={post.isPending} onClick={() => post.mutate(data.id)}>Post</Button>}</div></div>
    <Card><div className="grid gap-5 md:grid-cols-3 lg:grid-cols-6"><div><div className="text-xs text-slate-500">Source Purchase Order</div><Link className="font-medium text-emerald-700 hover:underline" to={`/purchase-orders/${data.purchase_order_id}`}>{data.purchase_order_number}</Link></div><div><div className="text-xs text-slate-500">Supplier</div><div>{data.supplier_name ?? "—"}</div></div><div><div className="text-xs text-slate-500">Receipt Date</div><div>{new Date(data.received_at).toLocaleString()}</div></div><div><div className="text-xs text-slate-500">Destination</div><div>{data.destination_type === "WAREHOUSE" ? "Warehouse" : "Direct Use"}</div></div><div><div className="text-xs text-slate-500">Warehouse</div><div>{data.destination_type === "WAREHOUSE" ? data.warehouse_name ?? "—" : "—"}</div></div><div><div className="text-xs text-slate-500">Delivery Note</div><div>{data.delivery_note_number ?? "—"}</div></div></div></Card>
    <Card className="overflow-hidden p-0"><div className="border-b bg-slate-50 px-5 py-4 font-semibold">Received Items</div><table className="table-grid w-full text-sm"><thead><tr className="border-b"><th className="p-3 text-left">Item Code</th><th className="text-left">Item Name</th><th>UOM</th><th className="text-right">Quantity</th><th className="p-3 text-right">Unit Cost</th></tr></thead><tbody>{data.items.map((item) => <tr key={item.id} className="border-b"><td className="p-3">{item.product_code ?? "—"}</td><td className="font-medium">{item.product_name}</td><td>{item.uom ?? "—"}</td><td className="text-right">{item.quantity}</td><td className="p-3 text-right">{Number(item.unit_cost).toLocaleString()}</td></tr>)}</tbody></table></Card>
    <Card><h2 className="mb-3 font-semibold">Notes</h2><p className="text-sm text-slate-700">{data.notes || "No notes provided."}</p></Card>
    {actions?.can_manage_attachments !== false && <DocumentAttachments entityType="GOODS_RECEIPT" entityId={data.id}/>}
    {actions?.can_view_history !== false && <DocumentActivity events={data.activity_history}/>}
  </div>;
}
