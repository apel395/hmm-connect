from fastapi import APIRouter

from app.api.v1 import (
    accounting, ap_aging, approvals, ar_aging, audit_trail, auth, balance_sheet,
    cash_flow, chart_of_accounts, customer_payments, dashboard, document_attachments, document_drilldown, document_events,
    accounting_posting_rules, supplier_invoices,
    fiscal_periods, general_ledger, goods_receipts, inventory,
    journal_detail, journals, payments, products, profit_loss, historical_import,
    purchase_orders, purchase_requisitions, purchasing_documents,
    supplier_products, suppliers,
    trial_balance, users, warehouses, year_end,
)

api_router = APIRouter()

for router in (
    auth.router, approvals.router, products.router, suppliers.router, chart_of_accounts.router,
    supplier_products.router,
    purchase_requisitions.router, purchase_orders.router,
    purchasing_documents.router,
    goods_receipts.router, inventory.router, dashboard.router,
    accounting.router, accounting_posting_rules.router, supplier_invoices.router, general_ledger.router, journals.router,
    journal_detail.router, fiscal_periods.router, payments.router,
    customer_payments.router, trial_balance.router, profit_loss.router,
    balance_sheet.router, cash_flow.router, ap_aging.router, ar_aging.router,
    users.router, warehouses.router, year_end.router, audit_trail.router, document_drilldown.router,
    document_events.router,
    document_attachments.router, historical_import.router,
):
    api_router.include_router(router)
