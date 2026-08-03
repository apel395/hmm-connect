import { useEffect, useState } from "react";
import {
  BarChart3, Boxes, Building2, ChevronDown, CircleDollarSign, ClipboardList,
  FileBarChart, Files, Landmark, LayoutDashboard, PackageSearch, Settings,
  ShoppingCart, Users, Warehouse, X,
} from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import useAuthStore from "@/store/auth";

interface Props { open?: boolean; onClose?: () => void }
interface Child { title: string; url?: string; roles?: string[]; disabled?: boolean }
interface Group { title: string; icon: typeof LayoutDashboard; url?: string; roles?: string[]; children?: Child[] }

const groups: Group[] = [
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
  { title: "Master Data", icon: Building2, children: [
    { title: "Items", url: "/products" }, { title: "Suppliers", url: "/suppliers", roles: ["PURCHASING"] },
    { title: "Warehouses", url: "/warehouses" }, { title: "Departments", disabled: true }, { title: "Locations", disabled: true },
  ] },
  { title: "Purchasing", icon: ShoppingCart, children: [
    { title: "Purchase Requisition", url: "/purchase-requisitions" }, { title: "Purchase Order", url: "/purchase-orders" },
    { title: "Receiving", url: "/receiving", roles: ["WAREHOUSE", "PURCHASING"] },
    { title: "Purchasing Documents", url: "/purchasing-documents", roles: ["PURCHASING", "FINANCE"] },
    { title: "Approval Inbox", disabled: true },
  ] },
  { title: "Inventory", icon: Boxes, children: [
    { title: "Stock", url: "/inventory", roles: ["WAREHOUSE"] },
    { title: "Stock Movement", url: "/inventory/movements", roles: ["WAREHOUSE"] },
    { title: "Stock Adjustment", disabled: true },
  ] },
  { title: "Finance", icon: Landmark, roles: ["FINANCE"], children: [
    { title: "Chart of Accounts", url: "/chart-of-accounts" }, { title: "Posting Rules", url: "/posting-rules" },
    { title: "Supplier Invoices", url: "/supplier-invoices" }, { title: "Journal Entries", url: "/journal-entries" },
    { title: "Payments", url: "/payments" }, { title: "General Ledger", url: "/general-ledger" },
    { title: "Trial Balance", disabled: true }, { title: "Balance Sheet", disabled: true }, { title: "Profit & Loss", disabled: true },
  ] },
  { title: "Reports", icon: FileBarChart, children: [
    { title: "Purchasing Reports", url: "/audit", roles: ["ADMIN"] }, { title: "Inventory Reports", disabled: true }, { title: "Finance Reports", disabled: true },
  ] },
  { title: "Administration", icon: Settings, roles: ["ADMIN"], children: [
    { title: "Users", url: "/users" }, { title: "Roles", url: "/roles" }, { title: "Settings", url: "/settings" },
  ] },
];

export default function Sidebar({ open = false, onClose }: Props) {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const roleNames = (user?.roles ?? []).map((role) => role.name);
  const isAdmin = roleNames.includes("ADMIN");
  const allowed = (roles?: string[]) => !roles || isAdmin || roles.some((role) => roleNames.includes(role));
  const activeParent = groups.find((group) => group.children?.some((child) => child.url && location.pathname.startsWith(child.url)))?.title;
  const [expanded, setExpanded] = useState<string[]>(activeParent ? [activeParent] : []);
  useEffect(() => { if (activeParent) setExpanded((value) => value.includes(activeParent) ? value : [...value, activeParent]); }, [activeParent]);

  return <>
    {open && <button className="fixed inset-0 z-40 bg-black/40 lg:hidden" aria-label="Close navigation" onClick={onClose}/>}
    <aside className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-[#073F37] text-white transition-transform lg:sticky lg:top-0 lg:translate-x-0 ${open ? "translate-x-0" : "-translate-x-full"}`}>
      <div className="border-b border-white/10 px-5 py-6">
        <button className="absolute right-3 top-3 rounded-lg p-2 text-white/70 hover:bg-white/10 lg:hidden" aria-label="Close navigation" onClick={onClose}><X className="h-5 w-5"/></button>
        <div className="flex items-center gap-3"><div className="grid h-11 w-11 place-items-center rounded-xl border border-[#C49A4A]/60 bg-white/5 font-serif text-lg font-bold tracking-wider text-[#E4C57E]">HMM</div><div><div className="font-semibold tracking-wide">HMM-Connect</div><div className="text-xs text-emerald-100/70">Hotel Mutiara Merdeka</div><div className="mt-1 text-[9px] text-[#C49A4A]">★★★★</div></div></div>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3">
        {groups.filter((group) => allowed(group.roles)).map((group) => {
          const Icon = group.icon;
          if (group.url) return <NavLink key={group.title} to={group.url} onClick={onClose} className={({isActive}) => `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium ${isActive ? "bg-[#0F6758] text-white" : "text-emerald-50/75 hover:bg-white/10"}`}><Icon className="h-[18px] w-[18px]"/>{group.title}</NavLink>;
          const children = group.children?.filter((child) => allowed(child.roles)) ?? [];
          const isExpanded = expanded.includes(group.title);
          return <div key={group.title}>
            <button type="button" aria-expanded={isExpanded} onClick={() => setExpanded((value) => value.includes(group.title) ? value.filter((item) => item !== group.title) : [...value, group.title])} className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-emerald-50/75 hover:bg-white/10"><Icon className="h-[18px] w-[18px]"/><span className="flex-1 text-left">{group.title}</span><ChevronDown className={`h-4 w-4 transition ${isExpanded ? "rotate-180" : ""}`}/></button>
            {isExpanded && <div className="ml-5 border-l border-white/10 pl-3">{children.map((child) => child.disabled ? <div key={child.title} className="flex items-center justify-between px-3 py-2 text-sm text-emerald-100/35" title="Coming Soon"><span>{child.title}</span><span className="text-[9px] uppercase">Soon</span></div> : <NavLink key={child.title} to={child.url!} onClick={onClose} className={({isActive}) => `block rounded-lg px-3 py-2 text-sm ${isActive ? "bg-[#0F6758] text-white" : "text-emerald-50/70 hover:bg-white/10 hover:text-white"}`}>{child.title}</NavLink>)}</div>}
          </div>;
        })}
      </nav>
      <div className="border-t border-white/10 p-4 text-xs text-emerald-100/55"><div className="flex items-center gap-2"><BarChart3 className="h-4 w-4 text-[#C49A4A]"/>Premium hotel operations</div></div>
    </aside>
  </>;
}
