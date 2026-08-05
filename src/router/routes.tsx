import {
  createBrowserRouter,
  Navigate,
} from "react-router-dom";

import AppLayout from "@/layouts/AppLayout";
import AuthGuard from "@/components/guard/AuthGuard";

/* Authentication */
import LoginPage from "@/modules/auth/pages/LoginPage";
import SignupPage from "@/modules/auth/pages/SignupPage";

/* Dashboard */
import DashboardPage from "@/modules/dashboard/DashboardPage";

/* Purchasing */
import PurchaseRequisitionListPage from "@/modules/purchasing/requisition/pages/PurchaseRequisitionListPage";
import PurchaseRequisitionDetailPage from "@/modules/purchasing/requisition/pages/PurchaseRequisitionDetailPage";

import PurchaseOrderListPage from "@/modules/purchasing/purchase-order/pages/PurchaseOrderListPage";
import PurchaseOrderDetailPage from "@/modules/purchasing/purchase-order/pages/PurchaseOrderDetailPage";
import PurchasingDocumentsPage from "@/modules/purchasing-documents/PurchasingDocumentsPage";
import PrintDocumentPage from "@/modules/purchasing/print/PrintDocumentPage";
import PostingRulesPage from "@/modules/finance/posting-rules/PostingRulesPage";
import SupplierInvoiceListPage from "@/modules/finance/supplier-invoices/SupplierInvoiceListPage";
import SupplierInvoiceDetailPage from "@/modules/finance/supplier-invoices/SupplierInvoiceDetailPage";
import JournalListPage from "@/modules/finance/journals/JournalListPage";
import JournalDetailPage from "@/modules/finance/journals/JournalDetailPage";
import AccountingPrintPage from "@/modules/finance/AccountingPrintPage";
import PaymentListPage from "@/modules/finance/payments/PaymentListPage";
import PaymentDetailPage from "@/modules/finance/payments/PaymentDetailPage";
import GeneralLedgerPage from "@/modules/finance/general-ledger/GeneralLedgerPage";
import HistoricalImportPage from "@/modules/finance/historical-import/HistoricalImportPage";
import HistoricalImportDetailPage from "@/modules/finance/historical-import/HistoricalImportDetailPage";

import FinanceDashboardPage from "@/modules/finance/finance-dashboard/FinanceDashboardPage";
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
    path: "/signup",
    element: <SignupPage />,
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
        path: "purchasing-documents",
        element: <PurchasingDocumentsPage />,
      },
      { path: "purchase-requisitions/:id/print", element: <PrintDocumentPage kind="purchase-requisitions" /> },
      { path: "purchase-orders/:id/print", element: <PrintDocumentPage kind="purchase-orders" /> },
      { path: "receiving/:id/print", element: <PrintDocumentPage kind="goods-receipts" /> },
      { path: "posting-rules", element: <PostingRulesPage /> },
      { path: "supplier-invoices", element: <SupplierInvoiceListPage /> },
      { path: "supplier-invoices/:id", element: <SupplierInvoiceDetailPage /> },
      { path: "supplier-invoices/:id/print", element: <AccountingPrintPage kind="supplier-invoices" /> },
      { path: "journal-entries", element: <JournalListPage /> },
      { path: "journal-entries/:id", element: <JournalDetailPage /> },
      { path: "journal-entries/:id/print", element: <AccountingPrintPage kind="journal-entries" /> },
      { path: "payments", element: <PaymentListPage /> },
      { path: "payments/:id", element: <PaymentDetailPage /> },
      { path: "payments/:id/print", element: <AccountingPrintPage kind="payments" /> },
      { path: "general-ledger", element: <GeneralLedgerPage /> },
      { path: "historical-import", element: <HistoricalImportPage /> },
      { path: "historical-import/:id", element: <HistoricalImportDetailPage /> },
      { path: "finance-dashboard", element: <FinanceDashboardPage /> },

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
