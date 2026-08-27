"""Apply the approved operational role-permission matrix.

Revision ID: 20260827_standard_operational_roles
Revises: 20260827_invoice_due_location_repair
"""

from alembic import op
import sqlalchemy as sa


revision = "20260827_standard_operational_roles"
down_revision = "20260827_invoice_due_location_repair"
branch_labels = None
depends_on = None


ROLE_DESCRIPTIONS = {
    "SYSTEM_ADMINISTRATOR": "Full system administration and unrestricted operational access.",
    "GENERAL_MANAGER": "Executive monitoring and final approval access.",
    "GENERAL MANAGER": "Workflow-compatible General Manager final approval role.",
    "PURCHASING": "Purchasing operations for PR conversion, PO, suppliers, and receiving support.",
    "HO PURCHASING": "Head Office purchasing approval and procurement operations.",
    "WAREHOUSE": "Warehouse controller with warehouse master, receiving, inventory, Store Request, and Stock Opname operations.",
    "STORE": "Location store operator for receiving, inventory, Store Request, and Stock Opname.",
    "CHEF": "Location operational approver for PR, Market List, and Receiving workflows.",
    "PM/CAMP BOSS": "Location senior approver for PR, Market List, and Receiving workflows.",
    "FINANCE": "Accounts payable, supplier invoices, payments, journals, and finance reporting.",
    "DEPARTMENT": "Department requester for PR, Market List, and Store Request within assigned scope.",
    "AUDITOR": "Read-only audit and cross-module reporting access.",
    "VIEWER": "Read-only dashboard and reporting access.",
}

ALL_PERMISSIONS = {
    "dashboard.view", "approval.view", "approval.manage",
    "products.view", "products.manage", "suppliers.view", "suppliers.manage",
    "warehouse.view", "warehouse.manage",
    "pr.view", "pr.create", "pr.edit", "pr.submit", "pr.approve", "pr.convert", "pr.manage",
    "market_list.view", "market_list.create", "market_list.edit", "market_list.submit",
    "market_list.approve", "market_list.convert", "market_list.manage",
    "po.view", "po.create", "po.edit", "po.submit", "po.approve", "po.manage",
    "receiving.view", "receiving.manage", "inventory.view", "inventory.manage",
    "store_request.view", "store_request.manage", "stock_opname.view", "stock_opname.manage",
    "finance.view", "finance.manage", "ap.view", "ap.manage",
    "supplier_invoice.view", "supplier_invoice.create", "supplier_invoice.edit",
    "supplier_invoice.verify", "supplier_invoice.reject", "supplier_invoice.post",
    "supplier_invoice.void", "supplier_invoice.manage",
    "payment.view", "payment.manage", "journal.view", "journal.manage",
    "coa.view", "coa.manage", "reports.view", "reports.purchasing",
    "reports.inventory", "reports.finance", "reports.own", "audit.read",
    "admin.users.manage", "admin.roles.manage", "admin.settings.manage",
}

ROLE_PERMISSIONS = {
    "SYSTEM_ADMINISTRATOR": ALL_PERMISSIONS,
    "STORE": {
        "dashboard.view", "approval.view", "products.view", "warehouse.view",
        "pr.view", "pr.approve", "po.view",
        "receiving.view", "receiving.manage",
        "inventory.view", "inventory.manage",
        "store_request.view", "store_request.manage",
        "stock_opname.view", "stock_opname.manage",
        "reports.inventory",
    },
    "WAREHOUSE": {
        "dashboard.view", "approval.view", "products.view",
        "warehouse.view", "warehouse.manage", "po.view",
        "receiving.view", "receiving.manage",
        "inventory.view", "inventory.manage",
        "store_request.view", "store_request.manage",
        "stock_opname.view", "stock_opname.manage",
        "reports.inventory",
    },
    "CHEF": {
        "dashboard.view", "approval.view",
        "pr.view", "pr.approve",
        "market_list.view", "market_list.approve",
        "receiving.view", "store_request.view", "reports.own",
    },
    "PM/CAMP BOSS": {
        "dashboard.view", "approval.view",
        "pr.view", "pr.approve",
        "market_list.view", "market_list.approve",
        "po.view", "receiving.view", "store_request.view", "reports.own",
    },
    "PURCHASING": {
        "dashboard.view", "approval.view", "products.view",
        "suppliers.view", "suppliers.manage",
        "pr.view", "pr.convert",
        "po.view", "po.create", "po.edit", "po.submit", "po.approve", "po.manage",
        "receiving.view", "receiving.manage",
        "inventory.view", "reports.purchasing",
    },
    "HO PURCHASING": {
        "dashboard.view", "approval.view", "products.view",
        "suppliers.view", "suppliers.manage",
        "pr.view", "pr.approve", "pr.convert",
        "po.view", "po.approve", "po.manage",
        "receiving.view", "inventory.view", "reports.purchasing",
    },
    "FINANCE": {
        "dashboard.view", "approval.view",
        "finance.view", "finance.manage",
        "ap.view", "ap.manage",
        "supplier_invoice.view", "supplier_invoice.create", "supplier_invoice.edit",
        "supplier_invoice.verify", "supplier_invoice.reject", "supplier_invoice.post",
        "supplier_invoice.void", "supplier_invoice.manage",
        "payment.view", "payment.manage",
        "journal.view", "journal.manage", "coa.view",
        "reports.finance",
        "pr.view", "pr.approve", "po.view", "po.approve", "receiving.view",
    },
    "GENERAL MANAGER": {
        "dashboard.view", "approval.view", "approval.manage",
        "pr.view", "pr.approve", "po.view", "po.approve", "receiving.view",
        "inventory.view", "finance.view", "reports.view",
    },
    "GENERAL_MANAGER": {
        "dashboard.view", "approval.view", "approval.manage",
        "pr.view", "pr.approve", "po.view", "po.approve", "receiving.view",
        "inventory.view", "finance.view", "reports.view",
    },
    "DEPARTMENT": {
        "dashboard.view", "approval.view",
        "pr.view", "pr.create", "pr.edit", "pr.submit",
        "market_list.view", "market_list.create", "market_list.edit", "market_list.submit",
        "store_request.view", "store_request.manage", "reports.own",
    },
    "AUDITOR": {
        "dashboard.view", "approval.view", "audit.read",
        "products.view", "suppliers.view", "warehouse.view",
        "pr.view", "market_list.view", "po.view", "receiving.view",
        "inventory.view", "store_request.view", "stock_opname.view",
        "finance.view", "ap.view", "supplier_invoice.view", "payment.view",
        "journal.view", "coa.view", "reports.view",
    },
    "VIEWER": {"dashboard.view", "reports.view"},
}


def _q(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def upgrade() -> None:
    bind = op.get_bind()

    for name, description in ROLE_DESCRIPTIONS.items():
        bind.execute(
            sa.text(
                """
                INSERT INTO roles (name, description)
                VALUES (:name, :description)
                ON CONFLICT (name) DO UPDATE
                SET description = EXCLUDED.description
                """
            ),
            {"name": name, "description": description},
        )

    permission_values = ", ".join(
        f"({_q(code)}, {_q(code.replace('.', ' ').replace('_', ' ').title())})"
        for code in sorted(ALL_PERMISSIONS)
    )
    op.execute(
        f"""
        INSERT INTO permissions (code, description)
        VALUES {permission_values}
        ON CONFLICT (code) DO NOTHING
        """
    )

    role_names = ", ".join(_q(name) for name in ROLE_PERMISSIONS)
    op.execute(
        f"""
        DELETE FROM role_permissions
        WHERE role_id IN (
            SELECT id FROM roles WHERE name IN ({role_names})
        )
        """
    )

    grants = [
        (role_name, permission_code)
        for role_name, permissions in ROLE_PERMISSIONS.items()
        for permission_code in sorted(permissions)
    ]
    grant_values = ", ".join(
        f"({_q(role_name)}, {_q(permission_code)})"
        for role_name, permission_code in grants
    )
    op.execute(
        f"""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM (VALUES {grant_values}) AS grants(role_name, permission_code)
        JOIN roles r ON r.name = grants.role_name
        JOIN permissions p ON p.code = grants.permission_code
        ON CONFLICT DO NOTHING
        """
    )


def downgrade() -> None:
    # Role mappings are live administrator-managed business configuration.
    # Downgrade intentionally leaves the applied matrix intact.
    pass
