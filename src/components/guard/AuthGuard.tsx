import { ReactNode, useEffect } from "react";
import { Navigate, useLocation } from "react-router-dom";

import Loading from "@/components/ui/Loading";
import { canAccess } from "@/lib/access";
import useAuthStore from "@/store/auth";

interface AuthGuardProps {
  children: ReactNode;
}

interface RouteAccess {
  prefix: string;
  permission: string;
  legacyRoles: string[];
}

const ROUTE_ACCESS: RouteAccess[] = [
  { prefix: "/approval-configuration", permission: "approval.manage", legacyRoles: ["SYSTEM_ADMINISTRATOR"] },
  { prefix: "/approval-center", permission: "approval.view", legacyRoles: ["PURCHASING", "WAREHOUSE", "FINANCE", "DEPARTMENT", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/purchase-requisitions", permission: "pr.view", legacyRoles: ["REQUESTER", "PURCHASING", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/market-lists", permission: "market_list.view", legacyRoles: ["REQUESTER", "PURCHASING", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/purchase-orders", permission: "po.view", legacyRoles: ["PURCHASING", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/receiving", permission: "receiving.view", legacyRoles: ["WAREHOUSE", "PURCHASING", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/supplier-invoices", permission: "supplier_invoice.view", legacyRoles: ["FINANCE"] },
  { prefix: "/accounts-payable", permission: "ap.view", legacyRoles: ["FINANCE", "GENERAL_MANAGER", "AUDITOR", "VIEWER"] },
  { prefix: "/fiscal", permission: "fiscal.view", legacyRoles: ["FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/payments", permission: "payment.view", legacyRoles: ["FINANCE"] },
  { prefix: "/journal", permission: "journal.view", legacyRoles: ["FINANCE", "GENERAL_MANAGER", "AUDITOR", "VIEWER"] },
  { prefix: "/general-ledger", permission: "reports.finance", legacyRoles: ["FINANCE", "GENERAL_MANAGER", "AUDITOR", "VIEWER"] },
  { prefix: "/trial-balance", permission: "reports.finance", legacyRoles: ["FINANCE", "GENERAL_MANAGER", "AUDITOR", "VIEWER"] },
  { prefix: "/cash-", permission: "finance.view", legacyRoles: ["FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/finance", permission: "finance.view", legacyRoles: ["FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/balance-sheet", permission: "reports.view", legacyRoles: ["FINANCE", "GENERAL_MANAGER", "AUDITOR", "VIEWER"] },
  { prefix: "/profit-loss", permission: "reports.view", legacyRoles: ["FINANCE", "GENERAL_MANAGER", "AUDITOR", "VIEWER"] },
  { prefix: "/inventory", permission: "inventory.view", legacyRoles: ["WAREHOUSE", "PURCHASING", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/store-requests", permission: "store_request.view", legacyRoles: ["WAREHOUSE", "DEPARTMENT", "PURCHASING", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/stock-opnames", permission: "stock_opname.view", legacyRoles: ["WAREHOUSE", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/products", permission: "products.view", legacyRoles: ["PURCHASING", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/suppliers", permission: "suppliers.view", legacyRoles: ["PURCHASING", "FINANCE", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/warehouses", permission: "warehouse.view", legacyRoles: ["WAREHOUSE", "GENERAL_MANAGER", "AUDITOR"] },
  { prefix: "/users", permission: "admin.users.manage", legacyRoles: ["SYSTEM_ADMINISTRATOR"] },
  { prefix: "/roles", permission: "admin.roles.manage", legacyRoles: ["SYSTEM_ADMINISTRATOR"] },
  { prefix: "/settings", permission: "admin.settings.manage", legacyRoles: ["SYSTEM_ADMINISTRATOR"] },
  { prefix: "/organization-dimensions", permission: "admin.settings.manage", legacyRoles: ["SYSTEM_ADMINISTRATOR"] },
  { prefix: "/audit", permission: "audit.read", legacyRoles: ["AUDITOR"] },
  { prefix: "/dashboard", permission: "dashboard.view", legacyRoles: [] },
];

export default function AuthGuard({ children }: AuthGuardProps) {
  const location = useLocation();
  const { authenticated, loading, initialize, user } = useAuthStore();

  useEffect(() => {
    initialize();
  }, [initialize]);

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loading />
      </div>
    );
  }

  if (!authenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (location.pathname !== "/403") {
    const rule = ROUTE_ACCESS.find(({ prefix }) => prefix.endsWith("-") ? location.pathname.startsWith(prefix) : location.pathname === prefix || location.pathname.startsWith(`${prefix}/`));
    if (rule && !canAccess(user, rule.legacyRoles, rule.permission)) {
      return <Navigate to="/403" replace />;
    }
  }

  return <>{children}</>;
}
