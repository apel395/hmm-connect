import { Navigate, Route, Routes } from "react-router-dom";

import { AppLayout } from "./components/layout/AppLayout";
import DashboardPage from "./pages/DashboardPage";
import LoginPage from "./pages/LoginPage";
import UsersPage from "./pages/UsersPage";
import RolesPage from "./pages/RolesPage";
import ProductsPage from "./pages/ProductsPage";
import SuppliersPage from "./pages/SuppliersPage";
import PurchaseOrdersPage from "./pages/PurchaseOrdersPage";
import ItemMasterPage from "./pages/ItemMasterPage";
import InventoryPage from "./pages/InventoryPage";
import PurchaseRequisitionsPage from "./pages/PurchaseRequisitionsPage";
import WarehousesPage from "./pages/WarehousesPage";
import AuditLogsPage from "./pages/AuditLogsPage";
import FinancePage from "./pages/FinancePage";
import LocationsPage from "./pages/LocationsPage";
import ApprovalWorkflowsPage from "./pages/ApprovalWorkflowsPage";
import { ProtectedRoute } from "./routes/ProtectedRoute";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route index element={<DashboardPage />} />
          <Route path="/purchase-requisitions" element={<PurchaseRequisitionsPage />} />
          <Route path="/purchase-orders" element={<PurchaseOrdersPage />} />
          <Route path="/products" element={<ProductsPage />} />
          <Route path="/items" element={<ItemMasterPage />} />
          <Route path="/inventory" element={<InventoryPage />} />
          <Route path="/warehouses" element={<WarehousesPage />} />
          <Route path="/locations" element={<LocationsPage />} />
          <Route path="/approval-workflows" element={<ApprovalWorkflowsPage />} />
          <Route path="/suppliers" element={<SuppliersPage />} />
          <Route path="/users" element={<UsersPage />} />
          <Route path="/roles" element={<RolesPage />} />
          <Route path="/audit-logs" element={<AuditLogsPage />} />
          <Route path="/finance" element={<FinancePage />} />
          <Route path="/reports" element={<div className="text-slate-900">Reports coming next</div>} />
          <Route path="/settings" element={<div className="text-slate-900">Settings coming next</div>} />
        </Route>
      </Route>

      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
