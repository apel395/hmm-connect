import {
  BarChart3,
  Boxes,
  Building2,
  ClipboardList,
  FileBarChart,
  Files,
  Landmark,
  LayoutDashboard,
  Settings,
  ShoppingCart,
  Users,
  X,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import useAuthStore from "@/store/auth";

interface Props {
  open?: boolean;
  onClose?: () => void;
}

const menus = [
  { title: "Dashboard", url: "/dashboard", icon: LayoutDashboard },
  {
    title: "Purchase Requisitions",
    url: "/purchase-requisitions",
    icon: ClipboardList,
  },
  { title: "Purchase Order", url: "/purchase-orders", icon: ShoppingCart },
  {
    title: "Purchasing Documents",
    url: "/purchasing-documents",
    icon: Files,
    roles: ["PURCHASING", "FINANCE"],
  },
  { title: "Inventory", url: "/inventory", icon: Boxes, roles: ["WAREHOUSE"] },
  { title: "Suppliers", url: "/suppliers", icon: Building2, roles: ["PURCHASING"] },
  { title: "Finance", url: "/chart-of-accounts", icon: Landmark, roles: ["FINANCE"] },
  { title: "Users", url: "/users", icon: Users, roles: ["ADMIN"] },
  { title: "Reports", url: "/audit", icon: FileBarChart, roles: ["ADMIN"] },
  { title: "Settings", url: "/settings", icon: Settings, roles: ["ADMIN"] },
];

export default function Sidebar({ open = false, onClose }: Props) {
  const user = useAuthStore((state) => state.user);
  const roleNames = (user?.roles ?? []).map((role) => role.name);
  const isAdmin = roleNames.includes("ADMIN");
  const visibleMenus = menus.filter(
    (menu) =>
      !menu.roles ||
      isAdmin ||
      menu.roles.some((role) => roleNames.includes(role)),
  );

  return (
    <>
      {open && (
        <button
          className="fixed inset-0 z-40 bg-black/40 lg:hidden"
          aria-label="Close navigation"
          onClick={onClose}
        />
      )}
      <aside
        className={`fixed inset-y-0 left-0 z-50 flex w-64 flex-col bg-[#073F37] text-white transition-transform lg:sticky lg:top-0 lg:translate-x-0 ${
          open ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        <div className="border-b border-white/10 px-5 py-6">
          <button
            className="absolute right-3 top-3 rounded-lg p-2 text-white/70 hover:bg-white/10 lg:hidden"
            aria-label="Close navigation"
            onClick={onClose}
          >
            <X className="h-5 w-5" />
          </button>
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-xl border border-[#C49A4A]/60 bg-white/5 font-serif text-lg font-bold tracking-wider text-[#E4C57E]">
              HMM
            </div>
            <div>
              <div className="font-semibold tracking-wide">HMM Connect</div>
              <div className="text-xs text-emerald-100/70">Hotel Mutiara Merdeka</div>
              <div className="mt-1 flex gap-1 text-[9px] text-[#C49A4A]" aria-label="Four star hotel">
                <span>★</span><span>★</span><span>★</span><span>★</span>
              </div>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-1 overflow-y-auto p-3">
          <div className="px-3 pb-2 pt-3 text-[10px] font-semibold uppercase tracking-[0.2em] text-emerald-100/50">
            Hotel Administration
          </div>
          {visibleMenus.map(({ title, url, icon: Icon }) => (
            <NavLink
              key={url}
              to={url}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#C49A4A] ${
                  isActive
                    ? "bg-[#0F6758] text-white shadow-sm"
                    : "text-emerald-50/75 hover:bg-white/10 hover:text-white"
                }`
              }
            >
              <Icon className="h-[18px] w-[18px]" />
              {title}
            </NavLink>
          ))}
        </nav>

        <div className="border-t border-white/10 p-4 text-xs text-emerald-100/55">
          <div className="flex items-center gap-2">
            <BarChart3 className="h-4 w-4 text-[#C49A4A]" />
            Premium hotel operations
          </div>
        </div>
      </aside>
    </>
  );
}
