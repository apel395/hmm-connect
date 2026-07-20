import {
  BarChart3,
  ReceiptText,
  Box,
  ClipboardList,
  LayoutDashboard,
  LogOut,
  Settings,
  GitBranch,
  History,
  Shield,
  Users,
  Package,
  ShoppingCart,
  Warehouse,
  MapPin,
} from "lucide-react";

import { NavLink } from "react-router-dom";

import { logout } from "../../features/auth/useAuth";

const navigation = [
{
label: "Dashboard",
icon: LayoutDashboard,
path: "/",
},

{
label: "Item Master",
icon: Box,
path: "/items",
},

{
label: "Suppliers",
icon: Package,
path: "/suppliers",
},

{
label: "Purchase Requisitions",
icon: ClipboardList,
path: "/purchase-requisitions",
},

{
label: "Purchase Orders",
icon: ShoppingCart,
path: "/purchase-orders",
},

{
label: "Inventory",
icon: Warehouse,
path: "/inventory",
},

{
label: "Warehouses",
icon: Warehouse,
path: "/warehouses",
},

{
label: "Locations",
icon: MapPin,
path: "/locations",
},

{
label: "Users",
icon: Users,
path: "/users",
},

{
label: "Roles",
icon: Shield,
path: "/roles",
},

{
label: "Audit Log",
icon: History,
path: "/audit-logs",
},

{
label: "Finance",
icon: ReceiptText,
path: "/finance",
},

{
label: "Reports",
icon: BarChart3,
path: "/reports",
},

{
label: "Approval Workflows",
icon: GitBranch,
path: "/approval-workflows",
},

{
label: "Settings",
icon: Settings,
path: "/settings",
},
];

export function Sidebar() {
return ( <aside className="flex h-screen w-64 flex-col border-r border-slate-200 bg-white"> <div className="flex h-16 items-center gap-3 border-b border-slate-200 px-6"> <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-slate-900 text-xs font-bold tracking-tight text-white">
HMM </div>


    <div className="leading-tight">
      <p className="font-semibold text-slate-900">
        HMM Connect
      </p>

      <p className="text-xs text-slate-500">
        Enterprise Resource Planning
      </p>
    </div>
  </div>


  <nav className="flex-1 space-y-1 overflow-y-auto p-4">
    {navigation.map((item) => {
      const Icon = item.icon;

      return (
        <NavLink
          key={item.path}
          to={item.path}
          end={item.path === "/"}
          className={({ isActive }) =>
            `flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
              isActive
                ? "bg-slate-900 text-white shadow-sm"
                : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
            }`
          }
        >
          <Icon size={18} />

          <span>
            {item.label}
          </span>
        </NavLink>
      );
    })}
  </nav>


  <div className="border-t border-slate-200 p-4">
    <button
      onClick={logout}
      className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium text-slate-600 transition hover:bg-red-50 hover:text-red-600"
    >
      <LogOut size={18} />

      <span>
        Sign out
      </span>
    </button>
  </div>
</aside>


);
}
