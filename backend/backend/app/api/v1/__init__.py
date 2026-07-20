from fastapi import APIRouter


from app.api.v1.auth import (
    router as auth_router,
)

from app.api.v1.users import (
    router as users_router,
)

from app.api.v1.roles import (
    router as roles_router,
)


from app.api.v1.products import (
    router as products_router,
)

from app.api.v1.suppliers import (
    router as suppliers_router,
)

from app.api.v1.purchase_orders import (
    router as purchase_orders_router,
)

from app.api.v1.goods_receipt import (
    router as goods_receipt_router,
)

from app.api.v1.item_classification import (
    router as item_classification_router,
)

from app.api.v1.inventory import (
    router as inventory_router,
)

from app.api.v1.purchase_requisitions import (
    router as purchase_requisitions_router,
)

from app.api.v1.audit_logs import (
    router as audit_logs_router,
)


from app.api.v1.departments import (
    router as departments_router,
)

from app.api.v1.warehouses import (
    router as warehouses_router,
)

from app.api.v1.chart_of_accounts import (
    router as chart_of_accounts_router,
)

from app.api.v1.finance import (
    router as finance_router,
)

api_router = APIRouter()


api_router.include_router(
    auth_router,
)

api_router.include_router(
    users_router,
)

api_router.include_router(
    roles_router,
)

api_router.include_router(
    products_router,
)

api_router.include_router(
    suppliers_router,
)

api_router.include_router(
    purchase_orders_router,
)

api_router.include_router(
    goods_receipt_router,
)

api_router.include_router(
    item_classification_router,
)

api_router.include_router(
    inventory_router,
)

api_router.include_router(
    purchase_requisitions_router,
)
api_router.include_router(
    audit_logs_router,
)

api_router.include_router(
    departments_router,
)

api_router.include_router(
    warehouses_router,
)

api_router.include_router(
    chart_of_accounts_router,
)

api_router.include_router(
    finance_router,
)

from app.api.v1.locations import (
    router as locations_router,
)

from app.api.v1.approval_workflows import (
    router as approval_workflows_router,
)

from app.api.v1.approvals import (
    router as approvals_router,
)

api_router.include_router(
    locations_router,
)

api_router.include_router(
    approval_workflows_router,
)

api_router.include_router(
    approvals_router,
)
