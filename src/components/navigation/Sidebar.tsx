import { NavLink } from "react-router-dom";

import useAuthStore from "@/store/auth";

interface MenuItem {
  title: string;
  url: string;
  roles?: string[];
}

const menus: MenuItem[] = [
  { title: "Dashboard", url: "/" },
  { title: "Purchase Requisition", url: "/purchase-requisitions" },
  { title: "Purchase Orders", url: "/purchase-orders" },
  { title: "Inventory", url: "/inventory", roles: ["WAREHOUSE"] },
  { title: "Products", url: "/products", roles: ["PURCHASING"] },
  { title: "Suppliers", url: "/suppliers", roles: ["PURCHASING"] },
  { title: "COA", url: "/chart-of-accounts", roles: ["FINANCE"] },
  { title: "Audit", url: "/audit", roles: ["ADMIN"] },
  { title: "Users", url: "/users", roles: ["ADMIN"] },
  { title: "Roles", url: "/roles", roles: ["ADMIN"] },
  { title: "Settings", url: "/settings", roles: ["ADMIN"] },
];

export default function Sidebar() {
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
    <div className="h-screen w-64 border-r bg-white">
      <div className="border-b p-6 text-2xl font-bold">
        ERP
      </div>

      <nav className="flex flex-col p-3">
        {visibleMenus.map((menu) => (
          <NavLink
            key={menu.url}
            to={menu.url}
            className="rounded-lg px-4 py-3 hover:bg-slate-100"
          >
            {menu.title}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}