import ARInvoicePage from "@/modules/finance/accounts-receivable/ARInvoicePage";
import CashierPage from "@/modules/finance/cash-flow/CashierPage";
import BudgetListPage from "@/modules/finance/budgets/BudgetListPage";
import BudgetFormPage from "@/modules/finance/budgets/BudgetFormPage";
import BudgetDetailPage from "@/modules/finance/budgets/BudgetDetailPage";
import { createBrowserRouter, Navigate } from "react-router-dom";
import AppLayout from "@/layouts/AppLayout";
import AuthGuard from "@/components/guard/AuthGuard";
import PermissionGuard from "@/components/guard/PermissionGuard";
import LoginPage from "@/modules/auth/pages/LoginPage";
import SignupPage from "@/modules/auth/pages/SignupPage";
import DashboardPage from "@/modules/dashboard/DashboardPage";
import PurchaseRequisitionListPage from "@/modules/purchasing/requisition/pages/PurchaseRequisitionListPage";
import PurchaseRequisitionDetailPage from "@/modules/purchasing/requisition/pages/PurchaseRequisitionDetailPage";
import MarketListPage from "@/modules/purchasing/market-list/MarketListPage";
import MarketListDetailPage from "@/modules/purchasing/market-list/MarketListDetailPage";
import PurchaseOrderListPage from "@/modules/purchasing/purchase-order/pages/PurchaseOrderListPage";
import PurchaseOrderDetailPage from "@/modules/purchasing/purchase-order/pages/PurchaseOrderDetailPage";
import ReceivingPage from "@/modules/purchasing/goods-receipts/pages/ReceivingPage";
import ReceivingDetailPage from "@/modules/purchasing/goods-receipts/pages/ReceivingDetailPage";
import PurchasingDocumentsPage from "@/modules/purchasing-documents/PurchasingDocumentsPage";
import PrintDocumentPage from "@/modules/purchasing/print/PrintDocumentPage";
import PostingRulesPage from "@/modules/finance/posting-rules/PostingRulesPage";
import FiscalAccountPage from "@/modules/finance/fiscal/pages/FiscalAccountPage";
import FiscalReconciliationPage from "@/modules/finance/fiscal/pages/FiscalReconciliationPage";
import Lampiran1DPage from "@/modules/finance/fiscal/pages/Lampiran1DPage";
import Spt1771Page from "@/modules/finance/fiscal/pages/Spt1771Page";
import SupplierInvoiceListPage from "@/modules/finance/supplier-invoices/SupplierInvoiceListPage";
import SupplierInvoiceDetailPage from "@/modules/finance/supplier-invoices/SupplierInvoiceDetailPage";
import PaymentVoucherListPage from "@/modules/finance/payment-vouchers/pages/PaymentVoucherListPage";
import PaymentVoucherDetailPage from "@/modules/finance/payment-vouchers/pages/PaymentVoucherDetailPage";
import PaymentVoucherPrintPage from "@/modules/finance/payment-vouchers/pages/PaymentVoucherPrintPage";
import SupplierAdjustmentsPage from "@/modules/finance/supplier-adjustments/SupplierAdjustmentsPage";
import AccountsPayablePage from "@/modules/finance/accounts-payable/AccountsPayablePage";
import APReportingPage from "@/modules/finance/accounts-payable/APReportingPage";
import APMovementPage from "@/modules/finance/accounts-payable/APMovementPage";
import ARReportingPage from "@/modules/finance/accounts-receivable/ARReportingPage";
import APAgingPrintPage from "@/modules/finance/accounts-payable/APAgingPrintPage";
import APInvoicesPage from "@/modules/finance/accounts-payable/APInvoicesPage";
import APPaymentsPage from "@/modules/finance/accounts-payable/APPaymentsPage";
import APAdjustmentsPage from "@/modules/finance/accounts-payable/APAdjustmentsPage";
import JournalListPage from "@/modules/finance/journals/JournalListPage";
import JournalDetailPage from "@/modules/finance/journals/JournalDetailPage";
import JournalWorkspacePage from "@/modules/finance/journals/JournalWorkspacePage";
import JournalRegisterPrintPage from "@/modules/finance/journals/JournalRegisterPrintPage";
import AccountingPrintPage from "@/modules/finance/AccountingPrintPage";
import PaymentListPage from "@/modules/finance/payments/PaymentListPage";
import PaymentDetailPage from "@/modules/finance/payments/PaymentDetailPage";
import GeneralLedgerPage from "@/modules/finance/general-ledger/GeneralLedgerPage";
import GeneralLedgerPrintPage from "@/modules/finance/general-ledger/GeneralLedgerPrintPage";
import CashFlowDashboardPage from "@/modules/finance/cash-flow/CashFlowDashboardPage";
import CashAccountsPage from "@/modules/finance/cash-flow/CashAccountsPage";
import CashAccountActivityPage from "@/modules/finance/cash-flow/CashAccountActivityPage";
import CashFlowStatementPage from "@/modules/finance/cash-flow/CashFlowStatementPage";
import BankTransferListPage from "@/modules/finance/cash-flow/BankTransferListPage";
import BankTransferDetailPage from "@/modules/finance/cash-flow/BankTransferDetailPage";
import BankTransferPrintPage from "@/modules/finance/cash-flow/BankTransferPrintPage";
import CashBankWorkspacePage from "@/modules/finance/cash-flow/CashBankWorkspacePage";
import TrialBalancePage from "@/modules/finance/trial-balance/TrialBalancePage";
import TrialBalancePrintPage from "@/modules/finance/trial-balance/TrialBalancePrintPage";
import FinancialReportPrintPage from "@/modules/finance/financial-statements/FinancialReportPrintPage";
import BalanceSheetPage from "@/modules/finance/financial-statements/BalanceSheetPage";
import ProfitLossPage from "@/modules/finance/financial-statements/ProfitLossPage";
import FinanceDashboardPage from "@/modules/finance/finance-dashboard/FinanceDashboardPage";
import ReconciliationPage from "@/modules/finance/reconciliation/ReconciliationPage";
import StockConsolidationPage from "@/modules/finance/reconciliation/StockConsolidationPage";
import BankReconciliationListPage from "@/modules/finance/bank-reconciliation/BankReconciliationListPage";
import BankReconciliationDetailPage from "@/modules/finance/bank-reconciliation/BankReconciliationDetailPage";
import FixedAssetFormPage from "@/modules/finance/fixed-assets/FixedAssetFormPage";
import FixedAssetDetailPage from "@/modules/finance/fixed-assets/FixedAssetDetailPage";
import AssetCategoryPage from "@/modules/finance/fixed-assets/AssetCategoryPage";
import DepreciationRunsPage from "@/modules/finance/fixed-assets/DepreciationRunsPage";
import FixedAssetReportPage from "@/modules/finance/fixed-assets/FixedAssetReportPage";
import DepreciationReportPage from "@/modules/finance/fixed-assets/DepreciationReportPage";
import AmortizationPage from "@/modules/finance/fixed-assets/AmortizationPage";
import FixedAssetsWorkspacePage from "@/modules/finance/fixed-assets/FixedAssetsWorkspacePage";
import FinanceSetupWorkspacePage from "@/modules/finance/setup/FinanceSetupWorkspacePage";
import FinanceSetupPrintPage from "@/modules/finance/setup/FinanceSetupPrintPage";
import BankAccountFormPage from "@/modules/finance/setup/BankAccountFormPage";
import ApprovalCenterPage from "@/modules/approval/ApprovalCenterPage";
import ApprovalConfigurationPage from "@/modules/approval/ApprovalConfigurationPage";
import InventoryPage from "@/modules/warehouse/inventory/pages/InventoryPage";
import InventoryMovementPage from "@/modules/warehouse/inventory/pages/InventoryMovementPage";
import InventoryReportsPage from "@/modules/warehouse/inventory/pages/InventoryReportsPage";
import StoreRequestPage from "@/modules/warehouse/store-request/StoreRequestPage";
import StoreRequestDetailPage from "@/modules/warehouse/store-request/StoreRequestDetailPage";
import StoreRequestPrintPage from "@/modules/warehouse/store-request/StoreRequestPrintPage";
import PutAwayPage from "@/modules/warehouse/put-away/pages/PutAwayPage";
import StockOpnamePage from "@/modules/warehouse/stock-opname/StockOpnamePage";
import StockOpnameDetailPage from "@/modules/warehouse/stock-opname/StockOpnameDetailPage";
import StockOpnamePrintPage from "@/modules/warehouse/stock-opname/StockOpnamePrintPage";
import StockAdjustmentPage from "@/modules/warehouse/inventory-adjustment/pages/StockAdjustmentPage";
import PosRegisterPage from "@/modules/pos/pages/PosRegisterPage";
import PosSalesPage from "@/modules/pos/pages/PosSalesPage";
import PosReceiptPrintPage from "@/modules/pos/pages/PosReceiptPrintPage";
import PurchasingReportsPage from "@/modules/purchasing/reports/PurchasingReportsPage";
import ProductPage from "@/modules/master/products/pages/ProductPage";
import SupplierPage from "@/modules/master/suppliers/pages/SupplierPage";
import WarehousePage from "@/modules/master/warehouses/WarehousePage";
import ChartOfAccountPage from "@/modules/master/chart-of-accounts/pages/ChartOfAccountPage";
import UserPage from "@/modules/admin/users/UserPage";
import RolePage from "@/modules/admin/roles/RolePage";
import SettingPage from "@/modules/admin/settings/SettingPage";
import ActiveSessionsPage from "@/modules/admin/sessions/ActiveSessionsPage";
import OrganizationDimensionsPage from "@/modules/admin/organization/OrganizationDimensionsPage";
import AuditLogPage from "@/modules/audit/AuditLogPage";
import TraceabilityPage from "@/modules/audit/TraceabilityPage";
import ProfilePage from "@/modules/profile/ProfilePage";
import NotificationPage from "@/modules/notification/NotificationPage";
import NotFoundPage from "@/pages/errors/NotFoundPage";
import ForbiddenPage from "@/pages/errors/ForbiddenPage";
import UnauthorizedPage from "@/pages/errors/UnauthorizedPage";
import InternalServerErrorPage from "@/pages/errors/InternalServerErrorPage";
import useAuthStore from "@/store/auth";
import { canAccess } from "@/lib/access";

const LANDING_CANDIDATES = [
  { path: "/dashboard", permission: "dashboard.view" },
  { path: "/approval-center", permission: "approval.view" },
  { path: "/purchase-requisitions", permission: "pr.view" },
  { path: "/market-lists", permission: "market_list.view" },
  { path: "/purchase-orders", permission: "po.view" },
  { path: "/receiving", permission: "receiving.view" },
  { path: "/inventory", permission: "inventory.view" },
  { path: "/store-requests", permission: "store_request.view" },
  { path: "/pos", permission: "pos.view" },
  { path: "/products", permission: "products.view" },
  { path: "/finance-dashboard", permission: "finance.view" },
  { path: "/accounts-payable", permission: "ap.view" },
  { path: "/journal", permission: "journal.view" },
  { path: "/cash-flow-statement", permission: "reports.view" },
  { path: "/finance/fiscal/coa", permission: "fiscal.view" },
  { path: "/finance/fiscal/reconciliation", permission: "fiscal.view" },
  { path: "/finance/fiscal/spt-1771", permission: "fiscal.view" },
] as const;

// eslint-disable-next-line react-refresh/only-export-components
function RoleLanding() {
  const user = useAuthStore((state) => state.user);
  const target =
    LANDING_CANDIDATES.find((candidate) =>
      canAccess(user, undefined, candidate.permission),
    )?.path ?? "/profile";
  return <Navigate to={target} replace />;
}

const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  { path: "/signup", element: <SignupPage /> },
  {
    path: "/",
    element: <AuthGuard><AppLayout /></AuthGuard>,
    children: [
      { index: true, element: <RoleLanding /> },
      { path: "dashboard", element: <DashboardPage /> },
      { path: "approval-center", element: <ApprovalCenterPage /> },
      { path: "approval-configuration", element: <ApprovalConfigurationPage /> },
      { path: "purchase-requisitions", element: <PurchaseRequisitionListPage /> },
      { path: "purchase-requisitions/:id", element: <PurchaseRequisitionDetailPage /> },
      { path: "market-lists", element: <MarketListPage /> },
      { path: "market-lists/:id", element: <MarketListDetailPage /> },
      { path: "purchase-orders", element: <PurchaseOrderListPage /> },
      { path: "purchase-orders/:id", element: <PurchaseOrderDetailPage /> },
      { path: "purchasing-documents", element: <PurchasingDocumentsPage /> },
      { path: "receiving", element: <ReceivingPage /> },
      { path: "receiving/:id", element: <ReceivingDetailPage /> },
      { path: "purchase-requisitions/:id/print", element: <PrintDocumentPage kind="purchase-requisitions" /> },
      { path: "market-lists/:id/print", element: <PrintDocumentPage kind="market-lists" /> },
      { path: "purchase-orders/:id/print", element: <PrintDocumentPage kind="purchase-orders" /> },
      { path: "receiving/:id/print", element: <PrintDocumentPage kind="goods-receipts" /> },

      { path: "accounts-payable", element: <APReportingPage /> },
      { path: "accounts-payable/detail", element: <APReportingPage /> },
      { path: "accounts-payable/aging", element: <AccountsPayablePage /> },
      { path: "accounts-payable/movement", element: <APMovementPage /> },
      { path: "accounts-payable/aging/print", element: <APAgingPrintPage /> },
      { path: "accounts-payable/invoices", element: <APInvoicesPage /> },
      { path: "accounts-payable/payments", element: <APPaymentsPage /> },
      { path: "accounts-payable/adjustments", element: <APAdjustmentsPage /> },
      { path: "accounts-receivable", element: <ARReportingPage /> },
      { path: "accounts-receivable/detail", element: <ARReportingPage /> },
      { path: "accounts-receivable/aging", element: <ARReportingPage /> },
      { path: "supplier-invoices", element: <SupplierInvoiceListPage /> },
      { path: "supplier-invoices/:id", element: <SupplierInvoiceDetailPage /> },
      { path: "supplier-invoices/:id/print", element: <AccountingPrintPage kind="supplier-invoices" /> },
      { path: "finance/payment-vouchers", element: <PaymentVoucherListPage /> },
      { path: "finance/payment-vouchers/:id", element: <PaymentVoucherDetailPage /> },
      { path: "finance/payment-vouchers/:id/print", element: <PaymentVoucherPrintPage /> },
      { path: "payment-vouchers", element: <Navigate to="/finance/payment-vouchers" replace /> },
      { path: "supplier-adjustments", element: <SupplierAdjustmentsPage /> },
      { path: "payments", element: <PaymentListPage /> },
      { path: "payments/:id", element: <PaymentDetailPage /> },
      { path: "payments/:id/print", element: <AccountingPrintPage kind="payments" /> },

      { path: "cash-bank", element: <CashBankWorkspacePage section="overview" /> },
      { path: "cash-bank/accounts", element: <Navigate to="/finance-setup/bank-accounts" replace /> },
      { path: "cash-bank/transfers", element: <CashBankWorkspacePage section="transfers" /> },
      { path: "cash-bank/reconciliation", element: <CashBankWorkspacePage section="reconciliation" /> },
      { path: "cash-bank/cash-flow", element: <CashBankWorkspacePage section="cash-flow" /> },
      { path: "cash-flow", element: <CashFlowDashboardPage /> },
      { path: "cash-accounts", element: <CashAccountsPage /> },
      { path: "cash-accounts/:id", element: <CashAccountActivityPage /> },
      { path: "cash-flow-statement", element: <CashFlowStatementPage /> },
      { path: "bank-transfers", element: <BankTransferListPage /> },
      { path: "bank-transfers/:id", element: <BankTransferDetailPage /> },
      { path: "accounts-receivable/invoices/:id", element: <PermissionGuard permission="finance.view"><ARInvoicePage /></PermissionGuard> },
      { path: "accounts-receivable/invoices/:id/print", element: <PermissionGuard permission="finance.view"><ARInvoicePage /></PermissionGuard> },
      { path: "cash-bank/cashier", element: <PermissionGuard permission="finance.view"><CashierPage /></PermissionGuard> },
      { path: "cash-bank/petty-cash", element: <PermissionGuard permission="finance.view"><CashierPage petty /></PermissionGuard> },
      { path: "bank-transfers/:id/print", element: <BankTransferPrintPage /> },
      { path: "bank-reconciliations", element: <BankReconciliationListPage /> },
      { path: "bank-reconciliations/:id", element: <BankReconciliationDetailPage /> },

      { path: "journal", element: <JournalWorkspacePage section="journal" /> },
      { path: "journal/general-ledger", element: <JournalWorkspacePage section="general-ledger" /> },
      { path: "journal/trial-balance", element: <JournalWorkspacePage section="trial-balance" /> },
      { path: "journal/register/print", element: <JournalRegisterPrintPage /> },
      { path: "journal/trial-balance/print", element: <TrialBalancePrintPage /> },
      { path: "journal-entries", element: <JournalListPage /> },
      { path: "journal-entries/:id", element: <JournalDetailPage /> },
      { path: "journal-entries/:id/print", element: <AccountingPrintPage kind="journal-entries" /> },
      { path: "general-ledger", element: <GeneralLedgerPage /> },
      { path: "general-ledger/print", element: <GeneralLedgerPrintPage /> },
      { path: "trial-balance", element: <TrialBalancePage /> },
      { path: "trial-balance/print", element: <TrialBalancePrintPage /> },

      { path: "fixed-assets", element: <FixedAssetsWorkspacePage section="assets" /> },
      { path: "fixed-assets/categories", element: <FixedAssetsWorkspacePage section="categories" /> },
      { path: "fixed-assets/depreciation", element: <FixedAssetsWorkspacePage section="depreciation" /> },
      { path: "fixed-assets/amortization", element: <FixedAssetsWorkspacePage section="amortization" /> },
      { path: "fixed-assets/reports", element: <FixedAssetsWorkspacePage section="reports" /> },
      { path: "fixed-assets/new", element: <FixedAssetFormPage /> },
      { path: "fixed-assets/:id", element: <FixedAssetDetailPage /> },
      { path: "asset-categories", element: <AssetCategoryPage /> },
      { path: "depreciation-runs", element: <DepreciationRunsPage /> },
      { path: "reports/fixed-assets", element: <FixedAssetReportPage /> },
      { path: "reports/depreciation", element: <DepreciationReportPage /> },
      { path: "amortization", element: <AmortizationPage /> },

      { path: "finance-setup/reports", element: <FinanceSetupWorkspacePage section="reports" /> },
      { path: "finance-setup", element: <FinanceSetupWorkspacePage section="coa" /> },
      { path: "finance-setup/coa/print", element: <FinanceSetupPrintPage section="coa" /> },
      { path: "finance-setup/posting-rules/print", element: <FinanceSetupPrintPage section="posting-rules" /> },
      { path: "finance-setup/bank-accounts/print", element: <FinanceSetupPrintPage section="bank-accounts" /> },
      { path: "finance-setup/opening-balances/print", element: <FinanceSetupPrintPage section="opening-balances" /> },
      { path: "finance-setup/accounting-periods/print", element: <FinanceSetupPrintPage section="accounting-periods" /> },
      { path: "finance-setup/posting-rules", element: <FinanceSetupWorkspacePage section="posting-rules" /> },
      { path: "finance-setup/fiscal-periods", element: <Navigate to="/finance-setup/accounting-periods" replace /> },
      { path: "finance-setup/accounting-periods", element: <FinanceSetupWorkspacePage section="accounting-periods" /> },
      { path: "finance-setup/bank-accounts", element: <FinanceSetupWorkspacePage section="bank-accounts" /> },
      { path: "finance-setup/bank-accounts/new", element: <BankAccountFormPage /> },
      { path: "finance-setup/bank-accounts/:id/edit", element: <BankAccountFormPage /> },
      { path: "finance-setup/opening-balances", element: <FinanceSetupWorkspacePage section="opening-balances" /> },
      { path: "chart-of-accounts", element: <ChartOfAccountPage /> },
      { path: "posting-rules", element: <PostingRulesPage /> },
      { path: "finance/fiscal", element: <Navigate to="/finance/fiscal/coa" replace /> },
      { path: "finance/fiscal/coa", element: <PermissionGuard permission="fiscal.view" legacyRoles={["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"]}><FiscalAccountPage /></PermissionGuard> },
      { path: "finance/fiscal/reconciliation", element: <PermissionGuard permission="fiscal.view" legacyRoles={["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"]}><FiscalReconciliationPage /></PermissionGuard> },
      { path: "finance/fiscal/lampiran-1d", element: <PermissionGuard permission="fiscal.view" legacyRoles={["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"]}><Lampiran1DPage /></PermissionGuard> },
      { path: "finance/fiscal/spt-1771", element: <PermissionGuard permission="fiscal.view" legacyRoles={["SYSTEM_ADMINISTRATOR", "FINANCE", "GENERAL_MANAGER", "AUDITOR"]}><Spt1771Page /></PermissionGuard> },
      { path: "finance/fiscal/periods", element: <Navigate to="/finance-setup/accounting-periods" replace /> },
      { path: "fiscal", element: <Navigate to="/finance/fiscal/coa" replace /> },
      { path: "fiscal/coa", element: <Navigate to="/finance/fiscal/coa" replace /> },
      { path: "fiscal/reconciliation", element: <Navigate to="/finance/fiscal/reconciliation" replace /> },
      { path: "fiscal/balance-sheet", element: <Navigate to="/finance/fiscal/lampiran-1d" replace /> },
      { path: "fiscal/lampiran-1d", element: <Navigate to="/finance/fiscal/lampiran-1d" replace /> },
      { path: "fiscal/spt-1771", element: <Navigate to="/finance/fiscal/spt-1771" replace /> },
      { path: "fiscal/periods", element: <Navigate to="/finance-setup/accounting-periods" replace /> },
      { path: "fiscal-coa", element: <Navigate to="/finance/fiscal/coa" replace /> },
      { path: "fiscal-reconciliation", element: <Navigate to="/finance/fiscal/reconciliation" replace /> },
      { path: "spt-1771", element: <Navigate to="/finance/fiscal/spt-1771" replace /> },
      { path: "fiscal-balance-sheet", element: <Navigate to="/finance/fiscal/lampiran-1d" replace /> },
      { path: "fiscal-periods", element: <Navigate to="/finance-setup/accounting-periods" replace /> },
      { path: "opening-balances", element: <Navigate to="/finance-setup/opening-balances" replace /> },

      { path: "finance-dashboard", element: <FinanceDashboardPage /> },
      { path: "financial-reconciliation", element: <ReconciliationPage /> },
      { path: "financial-reconciliation/stock", element: <StockConsolidationPage /> },
      { path: "balance-sheet/print", element: <FinancialReportPrintPage kind="BALANCE_SHEET" /> },
      { path: "balance-sheet", element: <BalanceSheetPage /> },
      { path: "budgets", element: <BudgetListPage /> },
      { path: "budgets/new", element: <BudgetFormPage /> },
      { path: "budgets/:id/edit", element: <BudgetFormPage /> },
      { path: "budgets/:id", element: <BudgetDetailPage /> },
      { path: "profit-loss/print", element: <FinancialReportPrintPage kind="PROFIT_LOSS" /> },
      { path: "profit-loss", element: <ProfitLossPage /> },
      { path: "inventory", element: <InventoryPage /> },
      { path: "inventory/movements", element: <InventoryMovementPage /> },
      { path: "reports/inventory", element: <InventoryReportsPage /> },
      { path: "reports/purchasing", element: <PermissionGuard permission="reports.purchasing" legacyRoles={["SYSTEM_ADMINISTRATOR", "PURCHASING", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"]}><PurchasingReportsPage /></PermissionGuard> },
      { path: "stock-adjustments", element: <StockAdjustmentPage /> },
      { path: "store-requests", element: <StoreRequestPage /> },
      { path: "store-requests/:id", element: <StoreRequestDetailPage /> },
      { path: "store-requests/:id/print", element: <StoreRequestPrintPage /> },
      { path: "stock-opnames", element: <StockOpnamePage /> },
      { path: "stock-opnames/:id", element: <StockOpnameDetailPage /> },
      { path: "stock-opnames/:id/print", element: <StockOpnamePrintPage /> },
      { path: "put-away", element: <PutAwayPage /> },
      { path: "pos", element: <PermissionGuard permission="pos.view" legacyRoles={["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"]}><PosRegisterPage /></PermissionGuard> },
      { path: "pos/sales", element: <PermissionGuard permission="pos.view" legacyRoles={["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"]}><PosSalesPage /></PermissionGuard> },
      { path: "pos/sales/:id/print", element: <PermissionGuard permission="pos.view" legacyRoles={["SYSTEM_ADMINISTRATOR", "WAREHOUSE", "FINANCE", "GENERAL_MANAGER", "AUDITOR"]}><PosReceiptPrintPage /></PermissionGuard> },
      { path: "products", element: <ProductPage /> },
      { path: "suppliers", element: <SupplierPage /> },
      { path: "warehouses", element: <WarehousePage /> },
      { path: "users", element: <UserPage /> },
      { path: "roles", element: <RolePage /> },
      { path: "settings", element: <SettingPage /> },
      { path: "active-sessions", element: <ActiveSessionsPage /> },
      { path: "organization-dimensions", element: <OrganizationDimensionsPage /> },
      { path: "audit", element: <AuditLogPage /> },
      { path: "traceability/:documentType/:id", element: <TraceabilityPage /> },
      { path: "notifications", element: <NotificationPage /> },
      { path: "profile", element: <ProfilePage /> },
      { path: "403", element: <ForbiddenPage /> },
      { path: "401", element: <UnauthorizedPage /> },
      { path: "500", element: <InternalServerErrorPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);

export default router;
