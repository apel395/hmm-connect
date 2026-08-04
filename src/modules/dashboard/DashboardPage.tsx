import {
  AlertTriangle,
  BedDouble,
  Boxes,
  ClipboardList,
  ShoppingCart,
  TrendingUp,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import useAuthStore from "@/store/auth";
import { useInventory } from "@/modules/warehouse/inventory/useInventory";
import type { Inventory } from "@/modules/warehouse/inventory/types";
import { usePurchaseOrders } from "@/modules/purchasing/purchase-order/hooks/usePurchaseOrders";
import type { PurchaseOrder } from "@/modules/purchasing/purchase-order/types";
import { usePurchaseRequisitions } from "@/modules/purchasing/requisition/hooks/usePurchaseRequisitions";
import type { PurchaseRequisition } from "@/modules/purchasing/requisition/types";

type ListEnvelope<T> = T[] | { items?: T[]; data?: T[] };

function listFrom<T>(value: unknown): T[] {
  if (Array.isArray(value)) return value as T[];
  if (value && typeof value === "object") {
    const envelope = value as ListEnvelope<T>;
    if ("items" in envelope && Array.isArray(envelope.items)) return envelope.items;
    if ("data" in envelope && Array.isArray(envelope.data)) return envelope.data;
  }
  return [];
}

const idr = new Intl.NumberFormat("id-ID", {
  style: "currency",
  currency: "IDR",
  maximumFractionDigits: 0,
});

const dateFormatter = new Intl.DateTimeFormat("en-US", {
  weekday: "long",
  day: "numeric",
  month: "long",
  year: "numeric",
});

const statusStyles: Record<string, string> = {
  DRAFT: "bg-stone-100 text-stone-700",
  PENDING_APPROVAL: "bg-amber-50 text-amber-800",
  APPROVED: "bg-emerald-50 text-emerald-800",
  PARTIALLY_RECEIVED: "bg-teal-50 text-teal-800",
  RECEIVED: "bg-[#E8F3EF] text-[#086B5A]",
  REJECTED: "bg-red-50 text-[#A44741]",
  CANCELLED: "bg-red-50 text-[#A44741]",
};

function Panel({
  title,
  action,
  children,
  className = "",
}: {
  title: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-xl border border-[#E8E2D8] bg-white shadow-[0_2px_12px_rgba(40,48,43,0.04)] ${className}`}>
      <div className="flex items-center justify-between border-b border-[#EEE9E0] px-5 py-4">
        <h2 className="font-serif text-lg font-semibold text-[#202723]">{title}</h2>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </section>
  );
}

function MiniTrend({ color }: { color: string }) {
  return (
    <svg viewBox="0 0 96 28" className="h-7 w-24" aria-hidden="true">
      <path
        d="M2 23 C14 21, 18 12, 30 16 S48 21, 58 11 S78 5, 94 8"
        fill="none"
        stroke={color}
        strokeWidth="2"
        strokeLinecap="round"
      />
    </svg>
  );
}

function KpiCard({
  title,
  value,
  note,
  icon: Icon,
  color,
}: {
  title: string;
  value: string | number;
  note: string;
  icon: LucideIcon;
  color: string;
}) {
  return (
    <div className="rounded-xl border border-[#E8E2D8] bg-white p-5 shadow-[0_2px_12px_rgba(40,48,43,0.04)] transition hover:-translate-y-0.5 hover:shadow-md">
      <div className="flex items-start justify-between">
        <div className="grid h-10 w-10 place-items-center rounded-lg" style={{ backgroundColor: `${color}18`, color }}>
          <Icon className="h-5 w-5" />
        </div>
        <MiniTrend color={color} />
      </div>
      <div className="mt-2 text-2xl font-semibold tracking-tight">{value}</div>
      <div className="mt-1 text-sm font-semibold">{title}</div>
      <div className="mt-1 text-xs text-[#6F756F]">{note}</div>
    </div>
  );
}

function OccupancyChart() {
  const points = "20,104 105,83 190,91 275,58 360,68 445,40 530,47 615,27";
  const bars = [52, 67, 59, 78, 70, 86, 81];
  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-5 text-xs text-[#6F756F]">
        <span className="flex items-center gap-2"><i className="h-2 w-2 rounded-full bg-[#086B5A]" /> Occupancy</span>
        <span className="flex items-center gap-2"><i className="h-2 w-2 rounded-sm bg-[#C49A4A]/55" /> Revenue</span>
        <span className="ml-auto italic">Illustrative hotel data</span>
      </div>
      <svg viewBox="0 0 640 150" className="h-56 w-full" role="img" aria-label="Seven day illustrative occupancy and revenue chart">
        {[30, 70, 110].map((y) => (
          <line key={y} x1="20" x2="620" y1={y} y2={y} stroke="#EEE9E0" />
        ))}
        {bars.map((height, index) => (
          <rect
            key={index}
            x={47 + index * 84}
            y={130 - height}
            width="28"
            height={height}
            rx="4"
            fill="#C49A4A"
            opacity=".35"
          />
        ))}
        <polyline points={points} fill="none" stroke="#086B5A" strokeWidth="3" strokeLinejoin="round" strokeLinecap="round" />
        {points.split(" ").map((point) => {
          const [cx, cy] = point.split(",");
          return <circle key={point} cx={cx} cy={cy} r="4" fill="#fff" stroke="#086B5A" strokeWidth="2" />;
        })}
        {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day, index) => (
          <text key={day} x={61 + index * 84} y="147" textAnchor="middle" fontSize="10" fill="#6F756F">{day}</text>
        ))}
      </svg>
    </div>
  );
}

function ProcurementOverview({ orders }: { orders: PurchaseOrder[] }) {
  const groups = [
    ["Draft", orders.filter((order) => order.status === "DRAFT").length, "#8E8C83"],
    ["Pending Approval", orders.filter((order) => order.status === "PENDING_APPROVAL").length, "#C49A4A"],
    ["Approved", orders.filter((order) => order.status === "APPROVED").length, "#328474"],
    ["Received", orders.filter((order) => order.status.includes("RECEIVED")).length, "#086B5A"],
    ["Cancelled", orders.filter((order) => ["REJECTED", "CANCELLED"].includes(order.status)).length, "#C75D56"],
  ] as const;
  const total = groups.reduce((sum, group) => sum + group[1], 0);
  let offset = 0;

  return (
    <div className="grid items-center gap-6 sm:grid-cols-[150px_1fr]">
      <div className="relative mx-auto h-36 w-36">
        <svg viewBox="0 0 42 42" className="-rotate-90">
          <circle cx="21" cy="21" r="15.9" fill="none" stroke="#F0ECE4" strokeWidth="5" />
          {groups.map(([label, count, color]) => {
            const size = total ? (count / total) * 100 : 0;
            const element = (
              <circle
                key={label}
                cx="21"
                cy="21"
                r="15.9"
                fill="none"
                stroke={color}
                strokeWidth="5"
                strokeDasharray={`${size} ${100 - size}`}
                strokeDashoffset={-offset}
              />
            );
            offset += size;
            return element;
          })}
        </svg>
        <div className="absolute inset-0 grid place-content-center text-center">
          <strong className="text-2xl">{total}</strong>
          <span className="text-[10px] uppercase text-[#6F756F]">Orders</span>
        </div>
      </div>
      <div className="space-y-2.5">
        {groups.map(([label, count, color]) => (
          <div key={label} className="flex items-center gap-2 text-sm">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: color }} />
            <span className="flex-1 text-[#6F756F]">{label}</span>
            <strong>{count}</strong>
            <span className="w-10 text-right text-xs text-[#6F756F]">{total ? Math.round((count / total) * 100) : 0}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const ordersQuery = usePurchaseOrders();
  const requisitionsQuery = usePurchaseRequisitions();
  const inventoryQuery = useInventory();
  const orders = listFrom<PurchaseOrder>(ordersQuery.data);
  const requisitions = listFrom<PurchaseRequisition>(requisitionsQuery.data);
  const inventory = listFrom<Inventory>(inventoryQuery.data);
  const pendingRequests = requisitions.filter((item) =>
    ["DRAFT", "PENDING", "PENDING_APPROVAL", "SUBMITTED"].includes(item.status),
  );
  const lowStock = inventory.filter(
    (item) => item.available_quantity <= (item.minimum_stock ?? 0),
  );
  const firstName = (user?.full_name || user?.username || "Hotel User").trim().split(/\s+/)[0];
  const recentOrders = [...orders]
    .sort((a, b) => new Date(b.order_date).getTime() - new Date(a.order_date).getTime())
    .slice(0, 5);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="mb-1 text-sm text-[#6F756F]">{dateFormatter.format(new Date())}</p>
          <h1 className="font-serif text-2xl font-semibold tracking-tight">Good morning, {firstName}</h1>
          <p className="mt-1 text-sm text-[#6F756F]">Here is today&apos;s hotel operations overview.</p>
        </div>
        <Link
          to="/purchase-requisitions"
          className="inline-flex h-10 items-center justify-center gap-2 rounded-lg bg-[#086B5A] px-4 text-sm font-semibold text-white shadow-sm transition hover:bg-[#07594C] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#086B5A] focus-visible:ring-offset-2"
        >
          <ShoppingCart className="h-4 w-4" />
          Create Purchase Requisition
        </Link>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard title="Occupancy" value="78%" note="Illustrative room occupancy" icon={BedDouble} color="#086B5A" />
        <KpiCard title="Pending Purchase Requests" value={pendingRequests.length} note="Awaiting procurement action" icon={ClipboardList} color="#C49A4A" />
        <KpiCard title="Purchase Orders" value={orders.length} note="Current purchase orders" icon={ShoppingCart} color="#328474" />
        <KpiCard title="Low Stock Items" value={lowStock.length} note="At or below minimum stock" icon={AlertTriangle} color="#C75D56" />
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.55fr_1fr]">
        <Panel title="Occupancy & Revenue Trend"><OccupancyChart /></Panel>
        <Panel title="Procurement Overview"><ProcurementOverview orders={orders} /></Panel>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1fr_1.55fr]">
        <Panel
          title="Inventory Alerts"
          action={<Link to="/inventory" className="text-xs font-semibold text-[#086B5A] hover:underline">View inventory</Link>}
        >
          {inventoryQuery.isLoading ? (
            <p className="py-8 text-center text-sm text-[#6F756F]">Loading inventory…</p>
          ) : inventoryQuery.isError ? (
            <p className="py-8 text-center text-sm text-[#C75D56]">Inventory alerts could not be loaded.</p>
          ) : lowStock.length === 0 ? (
            <div className="py-8 text-center">
              <Boxes className="mx-auto mb-2 h-7 w-7 text-[#328474]" />
              <p className="text-sm font-medium">Stock levels look healthy</p>
              <p className="text-xs text-[#6F756F]">No items are at or below their minimum.</p>
            </div>
          ) : (
            <div className="divide-y divide-[#EEE9E0]">
              {lowStock.slice(0, 5).map((item) => (
                <div key={item.id} className="flex items-center gap-3 py-3 first:pt-0 last:pb-0">
                  <div className="grid h-9 w-9 place-items-center rounded-lg bg-red-50 text-[#C75D56]"><AlertTriangle className="h-4 w-4" /></div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold">{item.product_name}</div>
                    <div className="text-xs text-[#6F756F]">SKU {item.product_code}</div>
                  </div>
                  <div className="text-right text-xs">
                    <div><strong className="text-[#C75D56]">{item.available_quantity}</strong> current</div>
                    <div className="text-[#6F756F]">{item.minimum_stock ?? 0} minimum</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </Panel>

        <Panel title="Recent Purchase Orders">
          {ordersQuery.isLoading ? (
            <p className="py-12 text-center text-sm text-[#6F756F]">Loading purchase orders…</p>
          ) : ordersQuery.isError ? (
            <p className="py-12 text-center text-sm text-[#C75D56]">Purchase orders could not be loaded.</p>
          ) : recentOrders.length === 0 ? (
            <p className="py-12 text-center text-sm text-[#6F756F]">No purchase orders are available.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-left text-sm">
                <thead className="text-xs uppercase tracking-wide text-[#6F756F]">
                  <tr>
                    <th className="pb-3 font-medium">PO Number</th>
                    <th className="pb-3 font-medium">Supplier</th>
                    <th className="pb-3 font-medium">Date</th>
                    <th className="pb-3 text-right font-medium">Total (IDR)</th>
                    <th className="pb-3 font-medium">Status</th>
                    <th className="pb-3 font-medium">Expected Date</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#EEE9E0]">
                  {recentOrders.map((order) => (
                    <tr key={order.id} className="hover:bg-[#FAF8F4]">
                      <td className="py-3 font-semibold text-[#086B5A]">{order.po_number}</td>
                      <td className="py-3">{order.supplier_name || "—"}</td>
                      <td className="py-3 text-[#6F756F]">{new Date(order.order_date).toLocaleDateString("id-ID")}</td>
                      <td className="py-3 text-right font-medium">{idr.format(order.total_amount || 0)}</td>
                      <td className="py-3">
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${statusStyles[order.status] ?? "bg-stone-100 text-stone-700"}`}>
                          {order.status.replaceAll("_", " ")}
                        </span>
                      </td>
                      <td className="py-3 text-[#6F756F]">{order.expected_date ? new Date(order.expected_date).toLocaleDateString("id-ID") : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Panel>
      </div>

      <Panel title="Recent Activity" action={<TrendingUp className="h-4 w-4 text-[#C49A4A]" />}>
        <div className="py-7 text-center">
          <p className="text-sm font-medium">No recent activity available</p>
          <p className="mt-1 text-xs text-[#6F756F]">Operational activity will appear here when an activity feed is available.</p>
        </div>
      </Panel>
    </div>
  );
}
