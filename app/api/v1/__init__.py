from fastapi import APIRouter

from app.api.v1 import (
    accounting, ap_aging, approvals, ar_aging, audit_trail, auth, balance_sheet,
    cash_flow, customer_payments, dashboard, document_attachments, document_drilldown, document_events,
    fiscal_periods, general_ledger, goods_receipts, inventory,
    journal_detail, journals, payments, products, profit_loss,
    purchase_orders, purchase_requisitions, supplier_products, suppliers,
    trial_balance, warehouses, year_end,
)

api_router = APIRouter()

for router in (
    auth.router, approvals.router, products.router, suppliers.router,
    supplier_products.router,
    purchase_requisitions.router, purchase_orders.router,
    goods_receipts.router, inventory.router, dashboard.router,
    accounting.router, general_ledger.router, journals.router,
    journal_detail.router, fiscal_periods.router, payments.router,
    customer_payments.router, trial_balance.router, profit_loss.router,
    balance_sheet.router, cash_flow.router, ap_aging.router, ar_aging.router,
    warehouses.router, year_end.router, audit_trail.router, document_drilldown.router,
    document_events.router,
    document_attachments.router,
):
    api_router.include_router(router)
