import { AlertTriangle, Boxes, ClipboardCheck, ClipboardList, ShoppingCart } from "lucide-react";
import { Link } from "react-router-dom";
import useAuthStore from "@/store/auth";
import Card from "@/components/ui/Card";
import { useInventory } from "@/modules/warehouse/inventory/useInventory";
import type { Inventory } from "@/modules/warehouse/inventory/types";
import { usePurchaseOrders } from "@/modules/purchasing/purchase-order/hooks/usePurchaseOrders";
import type { PurchaseOrder } from "@/modules/purchasing/purchase-order/types";
import { usePurchaseRequisitions } from "@/modules/purchasing/requisition/hooks/usePurchaseRequisitions";
import type { PurchaseRequisition } from "@/modules/purchasing/requisition/types";
import { useAllGoodsReceipts } from "@/modules/purchasing/goods-receipts/hooks/useGoodsReceipts";

type ListEnvelope<T> = { items?: T[]; data?: T[] };
const listFrom = <T,>(value: unknown): T[] => {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object") {
    const envelope = value as ListEnvelope<T>;
    if (Array.isArray(envelope.items)) return envelope.items;
    if (Array.isArray(envelope.data)) return envelope.data;
  }
  return [];
};
const dateFormatter = new Intl.DateTimeFormat("en-US", { weekday: "long", day: "numeric", month: "long", year: "numeric" });

function Metric({ title, value, note, icon: Icon }: { title: string; value: number; note: string; icon: any }) {
  return <Card><div className="flex items-start justify-between"><div><div className="text-3xl font-semibold">{value}</div><div className="mt-1 font-medium">{title}</div><div className="mt-1 text-xs text-slate-500">{note}</div></div><div className="rounded-lg bg-emerald-50 p-3 text-emerald-700"><Icon size={20}/></div></div></Card>;
}

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const ordersQuery = usePurchaseOrders();
  const requisitionsQuery = usePurchaseRequisitions();
  const lowStockQuery = useInventory({ health: "LOW_STOCK", page: 1, page_size: 8 });
  const receiptsQuery = useAllGoodsReceipts();
  const orders = listFrom<PurchaseOrder>(ordersQuery.data);
  const requisitions = listFrom<PurchaseRequisition>(requisitionsQuery.data);
  const lowStockData = (lowStockQuery.data ?? {}) as { items?: Inventory[]; total_items?: number };
  const lowStock = lowStockData.items ?? [];
  const lowStockCount = Number(lowStockData.total_items ?? 0);
  const receipts = listFrom<any>(receiptsQuery.data);
  const pendingRequests = requisitions.filter((row) => ["DRAFT", "PENDING", "PENDING_APPROVAL", "SUBMITTED"].includes(row.status));
  const pendingOrders = orders.filter((row) => ["DRAFT", "PENDING_APPROVAL", "APPROVED", "PARTIALLY_RECEIVED"].includes(row.status));
  const waitingReceiving = receipts.filter((row) => row.approval_status === "PENDING");
  const readyReceiving = receipts.filter((row) => row.status === "DRAFT" && row.approval_status === "APPROVED");
  const recentOrders = [...orders].sort((a, b) => new Date(b.order_date).getTime() - new Date(a.order_date).getTime()).slice(0, 8);
  const firstName = (user?.full_name || user?.username || "User").trim().split(/\s+/)[0];

  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><div className="text-sm text-slate-500">{dateFormatter.format(new Date())}</div><h1 className="mt-1 text-2xl font-semibold">Good morning, {firstName}</h1><p className="text-sm text-slate-500">Purchasing, receiving, inventory, and finance operations overview.</p></div><Link to="/purchase-requisitions" className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white">Create Purchase Requisition</Link></div>
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-5"><Metric title="Pending PR" value={pendingRequests.length} note="Draft or awaiting approval" icon={ClipboardList}/><Metric title="Open PO" value={pendingOrders.length} note="Not fully received" icon={ShoppingCart}/><Metric title="RR Waiting Approval" value={waitingReceiving.length} note="Receiving Reports in approval" icon={ClipboardCheck}/><Metric title="RR Ready to Post" value={readyReceiving.length} note="Approved, stock not posted" icon={Boxes}/><Metric title="Reorder Required" value={lowStockCount} note="Warehouse stock at or below minimum" icon={AlertTriangle}/></div>
    <div className="grid gap-6 xl:grid-cols-2">
      <Card><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">Procurement Overview</h2><Link className="text-sm text-emerald-700" to="/purchase-orders">View Purchase Orders</Link></div><div className="grid gap-3 sm:grid-cols-2"><div className="rounded border p-4"><div className="text-sm text-slate-500">PR Pending Approval</div><div className="text-2xl font-semibold">{requisitions.filter((row) => row.status === "PENDING_APPROVAL").length}</div></div><div className="rounded border p-4"><div className="text-sm text-slate-500">PO Pending Approval</div><div className="text-2xl font-semibold">{orders.filter((row) => row.status === "PENDING_APPROVAL").length}</div></div><Link to="/receiving" className="rounded border p-4 hover:bg-slate-50"><div className="text-sm text-slate-500">RR Waiting Approval</div><div className="text-2xl font-semibold">{waitingReceiving.length}</div></Link><Link to="/receiving" className="rounded border p-4 hover:bg-slate-50"><div className="text-sm text-slate-500">RR Approved to Post</div><div className="text-2xl font-semibold">{readyReceiving.length}</div></Link></div></Card>
      <Card><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">Reorder Required</h2><Link className="text-sm text-emerald-700" to="/inventory?health=LOW_STOCK">View Inventory</Link></div>{lowStock.length ? <div className="divide-y">{lowStock.map((row) => <div key={row.id} className="flex items-center justify-between gap-5 py-3"><div className="min-w-0"><div className="truncate font-medium">{row.product_name}</div><div className="truncate text-xs text-slate-500">{row.product_code} · {row.warehouse_name}</div></div><div className="shrink-0 text-right"><div className="font-semibold text-red-700">{Number(row.quantity).toLocaleString()} {row.uom}</div><div className="text-xs text-slate-500">minimum {Number(row.minimum_stock).toLocaleString()} · shortage {Number(row.shortage).toLocaleString()}</div></div></div>)}</div> : <div className="py-10 text-center text-sm text-slate-500">No warehouse stock is at or below its minimum threshold.</div>}</Card>
    </div>
    <Card><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">Recent Purchase Orders</h2><Link className="text-sm text-emerald-700" to="/purchase-orders">View all</Link></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-sm"><thead><tr><th className="text-left">PO Number</th><th>Supplier</th><th>Order Date</th><th>Status</th></tr></thead><tbody>{recentOrders.map((row) => <tr key={row.id} className="border-t"><td><Link className="text-emerald-700" to={`/purchase-orders/${row.id}`}>{row.po_number}</Link></td><td>{row.supplier_name ?? "—"}</td><td>{row.order_date}</td><td>{row.status}</td></tr>)}</tbody></table></div></Card>
  </div>;
}
