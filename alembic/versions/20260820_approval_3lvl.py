"""configure three-level purchasing approval workflows

Revision ID: 20260820_approval_3lvl
Revises: 20260819_market_session
"""
from alembic import op
import sqlalchemy as sa

revision = "20260820_approval_3lvl"
down_revision = "20260819_market_session"
branch_labels = None
depends_on = None


def _normalize(value: str) -> str:
    return "_".join(
        part for part in "".join(ch if ch.isalnum() else " " for ch in value.upper()).split() if part
    )


def _roles(connection):
    return {_normalize(row.name): row.id for row in connection.execute(sa.text("SELECT id, name FROM roles")).fetchall()}


def _workflow(connection, code: str, name: str, entity_type: str):
    workflow_id = connection.execute(
        sa.text("SELECT id FROM approval_workflows WHERE code=:code"), {"code": code}
    ).scalar()
    if workflow_id is None:
        workflow_id = connection.execute(
            sa.text("""
                INSERT INTO approval_workflows (code, name, entity_type, is_active)
                VALUES (:code, :name, :entity_type, TRUE)
                RETURNING id
            """),
            {"code": code, "name": name, "entity_type": entity_type},
        ).scalar_one()
    else:
        connection.execute(
            sa.text("UPDATE approval_workflows SET name=:name, entity_type=:entity_type, is_active=TRUE WHERE id=:id"),
            {"id": workflow_id, "name": name, "entity_type": entity_type},
        )
    return workflow_id


def _replace_steps(connection, role_map, workflow_id: int, steps):
    missing = [role_name for _, _, role_name in steps if _normalize(role_name) not in role_map]
    if missing:
        raise RuntimeError("Required approval roles not found: " + ", ".join(missing))
    connection.execute(
        sa.text("DELETE FROM approval_workflow_steps WHERE workflow_id=:workflow_id"),
        {"workflow_id": workflow_id},
    )
    for step_order, step_name, role_name in steps:
        connection.execute(
            sa.text("""
                INSERT INTO approval_workflow_steps
                    (workflow_id, step_order, name, approver_role_id, department_id, location_id)
                VALUES
                    (:workflow_id, :step_order, :name, :approver_role_id, NULL, NULL)
            """),
            {
                "workflow_id": workflow_id,
                "step_order": step_order,
                "name": step_name,
                "approver_role_id": role_map[_normalize(role_name)],
            },
        )


def _definitions(local_steps, manager_steps):
    return (
        ("PR_APPROVAL", "Purchase Requisition Approval", "PURCHASE_REQUISITION", local_steps),
        ("ML_APPROVAL", "Market List Approval", "MARKET_LIST", local_steps),
        ("PO_APPROVAL", "Purchase Order Approval", "PURCHASE_ORDER", manager_steps),
        ("RR_APPROVAL", "Receiving Report Approval", "GOODS_RECEIPT", local_steps),
    )


def upgrade():
    connection = op.get_bind()
    role_map = _roles(connection)
    local_steps = (
        (1, "Store Approval", "STORE"),
        (2, "Chef Approval", "CHEF"),
        (3, "PM / Camp Boss Approval", "PM/CAMP BOSS"),
    )
    manager_steps = (
        (1, "Head Office Purchasing Approval", "HO PURCHASING"),
        (2, "Finance Approval", "FINANCE"),
        (3, "General Manager Approval", "GENERAL MANAGER"),
    )
    for code, name, entity_type, steps in _definitions(local_steps, manager_steps):
        workflow_id = _workflow(connection, code, name, entity_type)
        _replace_steps(connection, role_map, workflow_id, steps)


def downgrade():
    connection = op.get_bind()
    role_map = _roles(connection)
    six_level = (
        (1, "Store Approval", "STORE"),
        (2, "Chef Approval", "CHEF"),
        (3, "PM / Camp Boss Approval", "PM/CAMP BOSS"),
        (4, "Head Office Purchasing Approval", "HO PURCHASING"),
        (5, "Finance Approval", "FINANCE"),
        (6, "General Manager Approval", "GENERAL MANAGER"),
    )
    definitions = (
        ("PR_APPROVAL", "Purchase Requisition Approval", "PURCHASE_REQUISITION"),
        ("ML_APPROVAL", "Market List Approval", "MARKET_LIST"),
        ("PO_APPROVAL", "Purchase Order Approval", "PURCHASE_ORDER"),
        ("RR_APPROVAL", "Receiving Report Approval", "GOODS_RECEIPT"),
    )
    for code, name, entity_type in definitions:
        workflow_id = _workflow(connection, code, name, entity_type)
        _replace_steps(connection, role_map, workflow_id, six_level)
