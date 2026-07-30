import {
  createBrowserRouter,
  Navigate,
} from "react-router-dom";

import AppLayout from "@/layouts/AppLayout";
import AuthGuard from "@/components/guard/AuthGuard";

/* Authentication */
import LoginPage from "@/modules/auth/pages/LoginPage";

/* Dashboard */
import DashboardPage from "@/modules/dashboard/DashboardPage";

/* Purchasing */
import PurchaseRequisitionListPage from "@/modules/purchasing/requisition/pages/PurchaseRequisitionListPage";
import PurchaseRequisitionDetailPage from "@/modules/purchasing/requisition/pages/PurchaseRequisitionDetailPage";

import PurchaseOrderListPage from "@/modules/purchasing/purchase-order/pages/PurchaseOrderListPage";
import PurchaseOrderDetailPage from "@/modules/purchasing/purchase-order/pages/PurchaseOrderDetailPage";

/* Warehouse */

import InventoryPage from "@/modules/warehouse/inventory/pages/InventoryPage";
import InventoryMovementPage from "@/modules/warehouse/inventory/pages/InventoryMovementPage";
import PutAwayPage from "@/modules/warehouse/put-away/pages/PutAwayPage";

/* Master */
import ProductPage from "@/modules/master/products/pages/ProductPage";
import SupplierPage from "@/modules/master/suppliers/pages/SupplierPage";
import WarehousePage from "@/modules/master/warehouses/WarehousePage";
import ChartOfAccountPage from "@/modules/master/chart-of-accounts/pages/ChartOfAccountPage";

/* Administration */
import UserPage from "@/modules/admin/users/UserPage";
import RolePage from "@/modules/admin/roles/RolePage";
import SettingPage from "@/modules/admin/settings/SettingPage";

/* Others */
import AuditLogPage from "@/modules/audit/AuditLogPage";
import TraceabilityPage from "@/modules/audit/TraceabilityPage";
import ProfilePage from "@/modules/profile/ProfilePage";
import NotificationPage from "@/modules/notification/NotificationPage";

import NotFoundPage from "@/pages/errors/NotFoundPage";
import ForbiddenPage from "@/pages/errors/ForbiddenPage";
import UnauthorizedPage from "@/pages/errors/UnauthorizedPage";
import InternalServerErrorPage from "@/pages/errors/InternalServerErrorPage";

const router = createBrowserRouter([
  {
    path: "/login",
    element: <LoginPage />,
  },

  {
    path: "/",
    element: (
      <AuthGuard>
        <AppLayout />
      </AuthGuard>
    ),

    children: [
      {
        index: true,
        element: <Navigate to="/dashboard" replace />,
      },

      {
        path: "dashboard",
        element: <DashboardPage />,
      },

      {
        path: "purchase-requisitions",
        element: <PurchaseRequisitionListPage />,
      },
      {
        path: "purchase-requisitions/:id",
        element: <PurchaseRequisitionDetailPage />,
      },

      {
        path: "purchase-orders",
        element: <PurchaseOrderListPage />,
      },
      {
        path: "purchase-orders/:id",
        element: <PurchaseOrderDetailPage />,
      },

      

      {
        path: "inventory",
        element: <InventoryPage />,
      },
      {
        path: "inventory/movements",
        element: <InventoryMovementPage />,
      },

      {
        path: "put-away",
        element: <PutAwayPage />,
      },

      {
        path: "products",
        element: <ProductPage />,
      },

      {
        path: "suppliers",
        element: <SupplierPage />,
      },

      {
        path: "warehouses",
        element: <WarehousePage />,
      },

      {
        path: "chart-of-accounts",
        element: <ChartOfAccountPage />,
      },

      {
        path: "users",
        element: <UserPage />,
      },

      {
        path: "roles",
        element: <RolePage />,
      },

      {
        path: "settings",
        element: <SettingPage />,
      },

      {
        path: "audit",
        element: <AuditLogPage />,
      },
      {
        path: "traceability/:documentType/:id",
        element: <TraceabilityPage />,
      },

      {
        path: "notifications",
        element: <NotificationPage />,
      },

      {
        path: "profile",
        element: <ProfilePage />,
      },

      {
        path: "403",
        element: <ForbiddenPage />,
      },

      {
        path: "401",
        element: <UnauthorizedPage />,
      },

      {
        path: "500",
        element: <InternalServerErrorPage />,
      },

      {
        path: "*",
        element: <NotFoundPage />,
      },
    ],
  },

  {
    path: "*",
    element: <Navigate to="/" replace />,
  },
]);

export default router;