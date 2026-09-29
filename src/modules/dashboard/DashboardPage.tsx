import { useQuery } from "@tanstack/react-query";
import {
  AlertCircle, ArrowRight, Box, CheckCircle2, ClipboardCheck, ClipboardList,
  Clock3, Coins, PackageCheck, RefreshCw, ShoppingCart, TrendingUp,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Link } from "react-router-dom";
import api from "@/api/interceptor";
import Card from "@/components/ui/Card";
import { hasPermission } from "@/lib/access";
import useAuthStore from "@/store/auth";

type Order = {
  id: number; po_number: string; supplier_name: string | null; order_date: string;
  status: string; total_amount: string; currency: string;
};
type LowStock = {
  id: number; product_code: string; product_name: string; warehouse_name: string;
  quantity: string; minimum_stock: string; shortage: string; uom: string;
};
type Overview = {
  generated_at: string;
  scope: { location_id: number | null; location_name: string | null };
  purchasing: {
    pr_waiting?: number; pr_draft?: number; po_waiting?: number; po_open?: number;
    rr_waiting?: number; rr_ready?: number; recent_orders?: Order[];
  };
  inventory: null | {
    stock_lines: number; stock_value: string; reorder_required: number; low_stock: LowStock[];
    by_account: { account_id: number | null; stock_value: string }[];
  };
  finance: null | { ap_outstanding: string; ap_overdue: string; overdue_invoice_count: number };
};
type QueueItem = {
  label: string; value: number; detail: string; href: string; icon: LucideIcon; tone: "amber" | "blue" | "emerald";
};
const number = (value: number | string) => Number(value || 0).toLocaleString("id-ID");
const rupiah = (value: number | string) => new Intl.NumberFormat("id-ID", {
  style: "currency", currency: "IDR", maximumFractionDigits: 0,
}).format(Number(value || 0));
const shortDate = (value: string) => new Intl.DateTimeFormat("en-GB", {
  day: "2-digit", month: "short", year: "numeric",
}).format(new Date(value));
const statusLabel = (status: string) => status.replaceAll("_", " ").toLowerCase()
  .replace(/\b\w/g, (letter) => letter.toUpperCase());

function SectionHeading({ eyebrow, title, href, link }: {
  eyebrow: string; title: string; href?: string; link?: string;
}) {
  return <div className="flex flex-wrap items-end justify-between gap-3">
    <div><p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-emerald-700">{eyebrow}</p>
      <h2 className="mt-1 text-lg font-semibold tracking-tight text-slate-900">{title}</h2></div>
    {href && <Link to={href} className="inline-flex items-center gap-1 text-sm font-medium text-emerald-700 hover:text-emerald-900">
      {link ?? "View all"} <ArrowRight size={15} /></Link>}
  </div>;
}

function QueueCard({ item }: { item: QueueItem }) {
  const Icon = item.icon;
  const tone = {
    amber: "bg-amber-50 text-amber-700", blue: "bg-sky-50 text-sky-700",
    emerald: "bg-emerald-50 text-emerald-700",
  }[item.tone];
  return <Link to={item.href} className="group rounded-2xl border border-slate-200 bg-white p-5 shadow-sm transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-md">
    <div className="flex items-start justify-between gap-3">
      <span className={"rounded-xl p-2.5 " + tone}><Icon size={19} /></span>
      <ArrowRight size={16} className="text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-emerald-700" />
    </div>
    <div className="mt-5 text-3xl font-semibold tabular-nums text-slate-950">{number(item.value)}</div>
    <div className="mt-1 text-sm font-semibold text-slate-800">{item.label}</div>
    <div className="mt-1 text-xs text-slate-500">{item.detail}</div>
  </Link>;
}

export default function DashboardPage() {
  const user = useAuthStore((state) => state.user);
  const query = useQuery({
    queryKey: ["dashboard", "overview", user?.id],
    queryFn: async () => (await api.get<Overview>("/dashboard/overview")).data,
    staleTime: 30_000,
    refetchInterval: 120_000,
  });
  const data = query.data;
  const p = data?.purchasing;
  const firstName = (user?.full_name || user?.username || "there").trim().split(/\s+/)[0];
  const localHour = Number(new Intl.DateTimeFormat("en-GB", {
    hour: "numeric", hourCycle: "h23", timeZone: "Asia/Jakarta",
  }).format(new Date()));
  const greeting = localHour < 11 ? "Good morning" : localHour < 16 ? "Good afternoon" : "Good evening";
  const today = new Intl.DateTimeFormat("en-GB", {
    weekday: "long", day: "numeric", month: "long", year: "numeric", timeZone: "Asia/Jakarta",
  }).format(new Date());
  const queue: QueueItem[] = [];
  if (p?.pr_waiting !== undefined) queue.push({ label: "PR awaiting approval", value: p.pr_waiting, detail: "Purchase requests to review", href: "/purchase-requisitions", icon: ClipboardList, tone: "amber" });
  if (p?.po_waiting !== undefined) queue.push({ label: "PO awaiting approval", value: p.po_waiting, detail: "Orders pending a decision", href: "/purchase-orders", icon: ShoppingCart, tone: "amber" });
  if (p?.po_open !== undefined) queue.push({ label: "Open purchase orders", value: p.po_open, detail: "Approved or partially received", href: "/purchase-orders", icon: PackageCheck, tone: "blue" });
  if (p?.rr_waiting !== undefined) queue.push({ label: "Receiving approval", value: p.rr_waiting, detail: "Reports in approval", href: "/receiving", icon: ClipboardCheck, tone: "amber" });
  if (p?.rr_ready !== undefined) queue.push({ label: "Ready to post", value: p.rr_ready, detail: "Approved receiving reports", href: "/receiving", icon: Box, tone: "emerald" });
  if (data?.inventory) queue.push({ label: "Reorder required", value: data.inventory.reorder_required, detail: "Stock at or below minimum", href: "/inventory?health=LOW_STOCK", icon: AlertCircle, tone: "amber" });
  const outstanding = queue.reduce((sum, item) => sum + item.value, 0);
  const recent = p?.recent_orders ?? [];
  const stock = data?.inventory;
  const finance = data?.finance;

  return <div className="mx-auto max-w-[1600px] space-y-7 pb-10">
    <header className="relative overflow-hidden rounded-2xl bg-slate-900 px-6 py-7 text-white sm:px-8 sm:py-8">
      <div className="pointer-events-none absolute -right-16 -top-32 h-80 w-80 rounded-full bg-emerald-500/15 blur-3xl" />
      <div className="relative flex flex-wrap items-end justify-between gap-5">
        <div><p className="text-xs font-medium uppercase tracking-[0.18em] text-emerald-300">{today}</p>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight sm:text-3xl">{greeting}, {firstName}.</h1>
          <p className="mt-2 max-w-xl text-sm text-slate-300">Your operations at a glance. Follow the queues below to keep purchasing, stock, and payables moving.</p>
          <p className="mt-4 flex items-center gap-2 text-xs text-slate-400">
            <span className="h-2 w-2 rounded-full bg-emerald-400" />
            {data?.scope.location_name ?? (data?.scope.location_id ? "Assigned location" : "All locations")}
            {data?.generated_at && " · Updated " + new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Jakarta" }).format(new Date(data.generated_at)) + " WIB"}
          </p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => void query.refetch()} disabled={query.isFetching}
            className="inline-flex items-center gap-2 rounded-lg border border-white/20 px-3 py-2 text-sm font-medium text-white hover:bg-white/10 disabled:opacity-60">
            <RefreshCw size={15} className={query.isFetching ? "animate-spin" : ""} /> Refresh
          </button>
          {hasPermission(user, "pr.view") && <Link to="/purchase-requisitions" className="inline-flex items-center gap-2 rounded-lg bg-emerald-500 px-3 py-2 text-sm font-semibold text-slate-950 hover:bg-emerald-400">
            Purchase requests <ArrowRight size={15} /></Link>}
        </div>
      </div>
    </header>

    {query.isPending && <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {[1, 2, 3, 4, 5, 6].map((value) => <div key={value} className="h-44 animate-pulse rounded-2xl bg-slate-100" />)}
    </div>}
    {query.isError && <Card className="p-6">
      <div className="flex items-center gap-3 text-rose-700"><AlertCircle size={20} /><span className="font-semibold">Dashboard could not load</span></div>
      <p className="mt-2 text-sm text-slate-600">Please retry. No figures are shown until the overview is available.</p>
      <button type="button" onClick={() => void query.refetch()} className="mt-4 text-sm font-semibold text-emerald-700">Try again</button>
    </Card>}

    {data && <>
      {queue.length > 0 && <section className="space-y-4">
        <SectionHeading eyebrow="Action center" title="Work that needs attention" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">{queue.map((item) => <QueueCard key={item.label} item={item} />)}</div>
        {outstanding === 0 && <p className="flex items-center gap-2 text-sm text-emerald-700"><CheckCircle2 size={17} /> All visible queues are clear.</p>}
      </section>}

      {(stock || finance) && <section className="space-y-4">
        <SectionHeading eyebrow="Position" title="Stock & finance" />
        <div className={"grid gap-4 " + (stock && finance ? "xl:grid-cols-2" : "")}>
          {stock && <Card className="p-5 sm:p-6">
            <div className="flex items-start justify-between gap-3"><div className="flex items-center gap-2 text-slate-900"><Box size={19} className="text-emerald-700" /><h3 className="font-semibold">Inventory position</h3></div>
              <Link to="/inventory" className="text-sm font-medium text-emerald-700 hover:underline">Explore inventory</Link></div>
            <div className="mt-6 text-3xl font-semibold tracking-tight text-slate-950">{rupiah(stock.stock_value)}</div>
            <p className="mt-1 text-sm text-slate-500">Current stock value across {number(stock.stock_lines)} product and warehouse lines</p>
            <div className="mt-6 grid grid-cols-2 gap-3 border-t border-slate-100 pt-5">
              <div><div className="text-xl font-semibold tabular-nums">{number(stock.reorder_required)}</div><div className="text-xs text-slate-500">Below or at minimum</div></div>
              <div><div className="text-xl font-semibold tabular-nums">{number(stock.by_account.length)}</div><div className="text-xs text-slate-500">Inventory account groups</div></div>
            </div>
          </Card>}
          {finance && <Card className="p-5 sm:p-6">
            <div className="flex items-center gap-2 text-slate-900"><Coins size={19} className="text-sky-700" /><h3 className="font-semibold">Payables position</h3></div>
            <div className="mt-6 text-3xl font-semibold tracking-tight text-slate-950">{rupiah(finance.ap_outstanding)}</div>
            <p className="mt-1 text-sm text-slate-500">Outstanding supplier invoices</p>
            <div className="mt-6 grid grid-cols-2 gap-3 border-t border-slate-100 pt-5">
              <div><div className="text-xl font-semibold tabular-nums text-amber-700">{rupiah(finance.ap_overdue)}</div><div className="text-xs text-slate-500">Overdue balance</div></div>
              <div><div className="text-xl font-semibold tabular-nums">{number(finance.overdue_invoice_count)}</div><div className="text-xs text-slate-500">Overdue invoices</div></div>
            </div>
          </Card>}
        </div>
      </section>}

      {(stock || p?.recent_orders) && <section className="grid gap-5 xl:grid-cols-5">
        {stock && <Card className="p-5 xl:col-span-2">
          <SectionHeading eyebrow="Stock watch" title="Reorder priorities" href="/inventory?health=LOW_STOCK" link="View inventory" />
          {stock.low_stock.length ? <div className="mt-4 divide-y divide-slate-100">{stock.low_stock.map((item) =>
            <div key={item.id} className="flex items-center justify-between gap-4 py-3">
              <div className="min-w-0"><div className="truncate text-sm font-medium text-slate-900">{item.product_name}</div>
                <div className="truncate text-xs text-slate-500">{item.product_code} · {item.warehouse_name}</div></div>
              <div className="shrink-0 text-right"><div className="text-sm font-semibold tabular-nums text-rose-700">{number(item.quantity)} {item.uom}</div>
                <div className="text-xs text-slate-500">Short {number(item.shortage)}</div></div>
            </div>)}</div> : <div className="mt-5 flex items-center gap-2 rounded-xl bg-emerald-50 p-4 text-sm text-emerald-800">
              <CheckCircle2 size={18} /> No monitored stock is below its minimum.</div>}
        </Card>}
        {p?.recent_orders && <Card className={"p-5 " + (stock ? "xl:col-span-3" : "xl:col-span-5")}>
          <SectionHeading eyebrow="Activity" title="Recent purchase orders" href="/purchase-orders" link="View all orders" />
          {recent.length ? <div className="mt-4 overflow-x-auto"><table className="w-full min-w-[540px] text-sm">
            <thead><tr className="border-b border-slate-100 text-left text-xs font-medium uppercase tracking-wide text-slate-500">
              <th className="py-3 pr-3">Order</th><th className="py-3 pr-3">Supplier</th><th className="py-3 pr-3">Date</th><th className="py-3">Status</th></tr></thead>
            <tbody>{recent.map((po) => <tr key={po.id} className="border-b border-slate-100 last:border-0">
              <td className="py-3 pr-3 font-semibold"><Link to={"/purchase-orders/" + po.id} className="text-emerald-700 hover:underline">{po.po_number}</Link></td>
              <td className="max-w-[190px] truncate py-3 pr-3 text-slate-700">{po.supplier_name ?? "—"}</td>
              <td className="whitespace-nowrap py-3 pr-3 text-slate-500">{shortDate(po.order_date)}</td>
              <td className="py-3"><span className="whitespace-nowrap rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-700">{statusLabel(po.status)}</span></td>
            </tr>)}</tbody></table></div> : <div className="mt-5 flex items-center gap-2 rounded-xl bg-slate-50 p-4 text-sm text-slate-600">
              <Clock3 size={18} /> No purchase orders yet.</div>}
        </Card>}
      </section>}
      {queue.length === 0 && !stock && !finance && <Card className="p-8 text-center text-slate-600">
        <TrendingUp className="mx-auto mb-3 text-emerald-600" size={28} />
        <h2 className="font-semibold text-slate-900">Welcome to your workspace</h2>
        <p className="mt-1 text-sm">Your dashboard will show the areas available to your role.</p>
      </Card>}
    </>}
  </div>;
}
