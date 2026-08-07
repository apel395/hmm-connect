import { AlertTriangle, Boxes, ClipboardList, ShoppingCart } from "lucide-react";
import { Link } from "react-router-dom";
import useAuthStore from "@/store/auth";
import Card from "@/components/ui/Card";
import { useInventory } from "@/modules/warehouse/inventory/useInventory";
import type { Inventory } from "@/modules/warehouse/inventory/types";
import { usePurchaseOrders } from "@/modules/purchasing/purchase-order/hooks/usePurchaseOrders";
import type { PurchaseOrder } from "@/modules/purchasing/purchase-order/types";
import { usePurchaseRequisitions } from "@/modules/purchasing/requisition/hooks/usePurchaseRequisitions";
import type { PurchaseRequisition } from "@/modules/purchasing/requisition/types";

type Envelope<T> = T[] | { items?: T[]; data?: T[] };
const listFrom = <T,>(value: unknown): T[] => {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object") {
    const envelope = value as Envelope<T>;
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
  const inventoryQuery = useInventory();
  const orders = listFrom<PurchaseOrder>(ordersQuery.data);
  const requisitions = listFrom<PurchaseRequisition>(requisitionsQuery.data);
  const inventory = listFrom<Inventory>(inventoryQuery.data);
  const pendingRequests = requisitions.filter((row) => ["DRAFT", "PENDING", "PENDING_APPROVAL", "SUBMITTED"].includes(row.status));
  const pendingOrders = orders.filter((row) => ["DRAFT", "PENDING_APPROVAL", "APPROVED", "PARTIALLY_RECEIVED"].includes(row.status));
  const lowStock = inventory.filter((row) => row.available_quantity <= (row.minimum_stock ?? 0));
  const recentOrders = [...orders].sort((a, b) => new Date(b.order_date).getTime() - new Date(a.order_date).getTime()).slice(0, 8);
  const firstName = (user?.full_name || user?.username || "User").trim().split(/\s+/)[0];

  return <div className="space-y-6">
    <div className="flex flex-wrap items-end justify-between gap-4"><div><div className="text-sm text-slate-500">{dateFormatter.format(new Date())}</div><h1 className="mt-1 text-2xl font-semibold">Good morning, {firstName}</h1><p className="text-sm text-slate-500">Purchasing, inventory, and finance operations overview.</p></div><Link to="/purchase-requisitions" className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-medium text-white">Create Purchase Requisition</Link></div>
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4"><Metric title="Pending Purchase Requests" value={pendingRequests.length} note="Draft or awaiting approval" icon={ClipboardList}/><Metric title="Open Purchase Orders" value={pendingOrders.length} note="Not fully received" icon={ShoppingCart}/><Metric title="Inventory Records" value={inventory.length} note="Tracked stock positions" icon={Boxes}/><Metric title="Low Stock Items" value={lowStock.length} note="At or below minimum stock" icon={AlertTriangle}/></div>
    <div className="grid gap-6 xl:grid-cols-2">
      <Card><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">Procurement Overview</h2><Link className="text-sm text-emerald-700" to="/purchase-orders">View Purchase Orders</Link></div><div className="grid gap-3 sm:grid-cols-2"><div className="rounded border p-4"><div className="text-sm text-slate-500">Draft PO</div><div className="text-2xl font-semibold">{orders.filter((row) => row.status === "DRAFT").length}</div></div><div className="rounded border p-4"><div className="text-sm text-slate-500">Pending Approval</div><div className="text-2xl font-semibold">{orders.filter((row) => row.status === "PENDING_APPROVAL").length}</div></div><div className="rounded border p-4"><div className="text-sm text-slate-500">Approved / Receivable</div><div className="text-2xl font-semibold">{orders.filter((row) => ["APPROVED", "PARTIALLY_RECEIVED"].includes(row.status)).length}</div></div><div className="rounded border p-4"><div className="text-sm text-slate-500">Fully Received</div><div className="text-2xl font-semibold">{orders.filter((row) => row.status === "RECEIVED").length}</div></div></div></Card>
      <Card><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">Inventory Alerts</h2><Link className="text-sm text-emerald-700" to="/inventory">View Inventory</Link></div>{lowStock.length ? <div className="divide-y">{lowStock.slice(0, 8).map((row) => <div key={row.id} className="flex items-center justify-between py-3"><div><div className="font-medium">{row.product_name}</div><div className="text-xs text-slate-500">{row.product_code}</div></div><div className="text-right"><div className="font-semibold text-red-600">{row.available_quantity}</div><div className="text-xs text-slate-500">minimum {row.minimum_stock ?? 0}</div></div></div>)}</div> : <div className="py-10 text-center text-sm text-slate-500">No low-stock items.</div>}</Card>
    </div>
    <Card><div className="mb-4 flex items-center justify-between"><h2 className="text-lg font-semibold">Recent Purchase Orders</h2><Link className="text-sm text-emerald-700" to="/purchase-orders">View all</Link></div><div className="overflow-x-auto"><table className="w-full min-w-[760px] text-sm"><thead><tr><th className="text-left">PO Number</th><th>Supplier</th><th>Order Date</th><th>Status</th></tr></thead><tbody>{recentOrders.map((row) => <tr key={row.id} className="border-t"><td><Link className="text-emerald-700" to={`/purchase-orders/${row.id}`}>{row.po_number}</Link></td><td>{row.supplier_name ?? "—"}</td><td>{row.order_date}</td><td>{row.status}</td></tr>)}</tbody></table></div></Card>
  </div>;
}
