import { useEffect, useState } from "react";
import axios from "axios";
import { ArrowLeft, FilePlus2, PencilLine, RotateCcw } from "lucide-react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { toast } from "sonner";
import Badge from "@/components/ui/Badge";
import Button from "@/components/ui/Button";
import Card from "@/components/ui/Card";
import Loading from "@/components/ui/Loading";
import Dialog, { DialogBody, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import CurrencyInput from "@/components/form/CurrencyInput";
import PrintPreviewButton from "@/components/print/PrintPreviewButton";
import DocumentAttachments from "@/modules/document-attachments/DocumentAttachments";
import { useCorrectGoodsReceiptCosts, useGoodsReceipt, usePostGoodsReceipt, useReturnGoodsReceipt } from "../hooks/useGoodsReceipts";
import DocumentActivity from "../../components/DocumentActivity";
import useAuthorization from "@/hooks/useAuthorization";

const money = (value: unknown) => Number(value ?? 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

export default function ReceivingDetailPage() {
  const navigate = useNavigate();
  const { id } = useParams();
  const { data, isLoading } = useGoodsReceipt(Number(id));
  const post = usePostGoodsReceipt();
  const returned = useReturnGoodsReceipt();
  const correctCosts = useCorrectGoodsReceiptCosts();
  const { canPerform } = useAuthorization();
  const [costDialogOpen, setCostDialogOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [costs, setCosts] = useState<Record<number, number>>({});

  useEffect(() => {
    if (!data) return;
    setCosts(Object.fromEntries(data.items.map((item) => [item.id, Number(item.unit_cost)])));
  }, [data]);

  if (isLoading) return <Loading/>;
  if (!data) return null;
  const actions = data.allowed_actions;
  const canReturn = canPerform("receive", ["WAREHOUSE", "PURCHASING"], actions?.can_return ?? false);
  const canCorrectCost = Boolean(actions?.can_correct_cost);
  const correctedTotal = data.items.reduce((sum, item) => sum + Number(item.quantity) * Number(costs[item.id] ?? item.unit_cost), 0);
  const changedItems = data.items.filter((item) => Number(costs[item.id] ?? item.unit_cost) !== Number(item.unit_cost));

  const submitCostCorrection = async () => {
    if (!changedItems.length) return toast.error("Change at least one unit cost.");
    if (reason.trim().length < 3) return toast.error("Correction reason is required.");
    if (changedItems.some((item) => Number(costs[item.id]) <= 0)) return toast.error("Unit cost must be greater than zero.");
    try {
      await correctCosts.mutateAsync({
        id: data.id,
        payload: { reason: reason.trim(), items: changedItems.map((item) => ({ item_id: item.id, unit_cost: Number(costs[item.id]) })) },
      });
      toast.success("Receiving cost corrected and audit history updated.");
      setReason("");
      setCostDialogOpen(false);
    } catch (error) {
      const detail = axios.isAxiosError(error) ? error.response?.data?.detail : null;
      toast.error(typeof detail === "string" ? detail : "Receiving cost could not be corrected.");
    }
  };

  return <div className="space-y-6">
    <div className="flex flex-wrap items-center justify-between gap-4">
      <div className="flex items-center gap-4"><Button variant="outline" size="sm" onClick={() => navigate("/receiving")}><ArrowLeft size={17}/> Back</Button><div><div className="text-sm text-slate-500">Receiving</div><div className="flex items-center gap-3"><h1 className="text-2xl font-bold">{data.receipt_number}</h1><Badge>{data.status}</Badge>{data.source_mode === "DIRECT" && <Badge variant="warning">Direct</Badge>}</div></div></div>
      <div className="flex flex-wrap gap-2">
        {data.status === "POSTED" && <Button onClick={() => navigate(`/supplier-invoices?receipt_id=${data.id}`)}><FilePlus2 size={16}/> Create Supplier Invoice</Button>}
        {canCorrectCost && <Button variant="outline" onClick={() => { setCosts(Object.fromEntries(data.items.map((item) => [item.id, Number(item.unit_cost)]))); setReason(""); setCostDialogOpen(true); }}><PencilLine size={16}/> Correct Cost</Button>}
        {actions?.can_print !== false && <PrintPreviewButton src={`/receiving/${data.id}/print`} title={`Receiving ${data.receipt_number}`} ariaLabel="Preview receiving document" />}
        {canPerform("post", ["WAREHOUSE", "PURCHASING"], actions?.can_post ?? false) && <Button loading={post.isPending} onClick={() => post.mutate(data.id)}>Post</Button>}
        {canReturn && <Button variant="danger" loading={returned.isPending} onClick={() => { if (window.confirm("Return all quantities from this receipt?")) returned.mutate(data.id, { onSuccess: () => toast.success("Receipt returned.") }); }}><RotateCcw size={16}/> Return</Button>}
      </div>
    </div>
    <Card><div className="grid gap-5 md:grid-cols-3 lg:grid-cols-6"><div><div className="text-xs text-slate-500">Source</div>{data.purchase_order_id ? <Link className="font-medium text-emerald-700 hover:underline" to={`/purchase-orders/${data.purchase_order_id}`}>{data.purchase_order_number}</Link> : <div>Direct Receiving</div>}</div><div><div className="text-xs text-slate-500">Supplier</div><div>{data.supplier_name ?? "—"}</div></div><div><div className="text-xs text-slate-500">Receipt Date</div><div>{new Date(data.received_at).toLocaleString()}</div></div><div><div className="text-xs text-slate-500">Destination</div><div>{data.destination_type === "WAREHOUSE" ? "Warehouse" : "Direct Use"}</div></div><div><div className="text-xs text-slate-500">Warehouse</div><div>{data.destination_type === "WAREHOUSE" ? data.warehouse_name ?? "—" : "—"}</div></div><div><div className="text-xs text-slate-500">Delivery Note</div><div>{data.delivery_note_number ?? "—"}</div></div></div></Card>
    <Card className="overflow-hidden p-0"><div className="border-b bg-slate-50 px-5 py-4 font-semibold">Received Items</div><div className="overflow-x-auto"><table className="table-grid min-w-[800px] w-full text-sm"><thead><tr className="border-b"><th className="p-3 text-left">Item Code</th><th className="text-left">Item Name</th><th>UOM</th><th className="text-right">Quantity</th><th className="text-right">Unit Cost</th><th className="p-3 text-right">Line Total</th></tr></thead><tbody>{data.items.map((item) => <tr key={item.id} className="border-b"><td className="p-3">{item.product_code ?? "—"}</td><td className="font-medium">{item.product_name}</td><td>{item.uom ?? "—"}</td><td className="text-right">{item.quantity}</td><td className={`text-right ${Number(item.unit_cost) <= 0 ? "font-semibold text-red-700" : ""}`}>{money(item.unit_cost)}</td><td className="p-3 text-right font-medium">{money(item.line_total ?? Number(item.quantity) * Number(item.unit_cost))}</td></tr>)}</tbody><tfoot><tr><td colSpan={5} className="p-3 text-right font-semibold">Total Cost</td><td className="p-3 text-right text-lg font-bold">{money(data.total_value ?? data.items.reduce((sum, item) => sum + Number(item.quantity) * Number(item.unit_cost), 0))}</td></tr></tfoot></table></div></Card>
    <Card><h2 className="mb-3 font-semibold">Notes</h2><p className="text-sm text-slate-700">{data.notes || "No notes provided."}</p></Card>
    {actions?.can_manage_attachments !== false && <DocumentAttachments entityType="GOODS_RECEIPT" entityId={data.id}/>} {actions?.can_view_history !== false && <DocumentActivity events={data.activity_history}/>} 

    <Dialog open={costDialogOpen} onOpenChange={setCostDialogOpen}><DialogContent className="max-w-4xl"><DialogHeader><DialogTitle>Correct Receiving Cost</DialogTitle></DialogHeader><DialogBody className="space-y-4">
      <div className="rounded border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">Cost corrections are restricted to administrators/authorized managers and are written to the audit history. If stock has already moved out or a supplier invoice exists, the backend will block historical revaluation.</div>
      <div className="overflow-x-auto rounded border"><table className="min-w-[760px] w-full text-sm"><thead className="bg-slate-50"><tr><th className="p-3 text-left">Item</th><th className="text-right">Qty</th><th className="text-right">Current Cost</th><th className="text-right">Corrected Cost</th><th className="p-3 text-right">Amount</th></tr></thead><tbody>{data.items.map((item) => <tr key={item.id} className="border-t"><td className="p-3"><div className="font-medium">{item.product_name}</div><div className="text-xs text-slate-500">{item.product_code}</div></td><td className="text-right">{item.quantity}</td><td className="text-right">{money(item.unit_cost)}</td><td className="p-2"><CurrencyInput value={Number(costs[item.id] ?? item.unit_cost)} onValueChange={(value) => setCosts((current) => ({ ...current, [item.id]: value }))}/></td><td className="p-3 text-right font-medium">{money(Number(item.quantity) * Number(costs[item.id] ?? item.unit_cost))}</td></tr>)}</tbody><tfoot><tr><td colSpan={4} className="p-3 text-right font-semibold">Corrected Total</td><td className="p-3 text-right text-base font-bold">{money(correctedTotal)}</td></tr></tfoot></table></div>
      <label className="block text-sm font-medium">Correction Reason *<textarea className="mt-1 min-h-24 w-full rounded-md border p-2" value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Explain the human-entry or document error being corrected."/></label>
    </DialogBody><DialogFooter><Button variant="outline" onClick={() => setCostDialogOpen(false)}>Cancel</Button><Button loading={correctCosts.isPending} onClick={submitCostCorrection}>Save Correction</Button></DialogFooter></DialogContent></Dialog>
  </div>;
}
