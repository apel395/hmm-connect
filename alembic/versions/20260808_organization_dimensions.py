"""Extend finance documents with organization dimensions.

Revision ID: 20260808_org_dimensions
Revises: 20260807_budget_management
"""
from alembic import op
import sqlalchemy as sa


revision = "20260808_org_dimensions"
down_revision = "20260807_budget_management"
branch_labels = None
depends_on = None


def upgrade():
    # Business Units and the Department/Location relationships are introduced
    # by 20260806_org_master_data. This revision only extends finance records.
    op.add_column("users", sa.Column("default_business_unit_id", sa.Integer(), sa.ForeignKey("business_units.id", ondelete="SET NULL")))
    op.add_column("users", sa.Column("default_location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="SET NULL")))
    op.add_column("users", sa.Column("default_department_id", sa.Integer(), sa.ForeignKey("departments.id", ondelete="SET NULL")))
    for column in ("default_business_unit_id", "default_location_id", "default_department_id"):
        op.create_index(f"ix_users_{column}", "users", [column])
    op.execute("UPDATE users SET default_location_id=location_id, default_department_id=department_id")
    op.execute("UPDATE users u SET default_business_unit_id=l.business_unit_id FROM locations l WHERE u.location_id=l.id")

    dimensions = {
        "purchase_requisitions": ["business_unit_id"],
        "purchase_orders": ["business_unit_id"],
        "supplier_invoices": ["business_unit_id"],
        "payments": ["business_unit_id", "location_id", "department_id"],
        "goods_receipts": ["business_unit_id", "location_id", "department_id"],
        "journal_entries": ["business_unit_id", "location_id", "department_id"],
        "journal_lines": ["business_unit_id"],
        "bank_reconciliations": ["business_unit_id", "location_id", "department_id"],
        "budget_lines": ["business_unit_id"],
    }
    targets = {
        "business_unit_id": "business_units.id",
        "location_id": "locations.id",
        "department_id": "departments.id",
    }
    for table, columns in dimensions.items():
        for column in columns:
            op.add_column(table, sa.Column(column, sa.Integer(), sa.ForeignKey(targets[column], ondelete="SET NULL")))
            op.create_index(f"ix_{table}_{column}", table, [column])

    for table in ("purchase_requisitions", "purchase_orders", "supplier_invoices"):
        op.execute(f"UPDATE {table} d SET business_unit_id=l.business_unit_id FROM locations l WHERE d.location_id=l.id")
    op.execute("UPDATE goods_receipts g SET business_unit_id=p.business_unit_id, location_id=p.location_id, department_id=p.department_id FROM purchase_orders p WHERE g.purchase_order_id=p.id")
    op.execute("UPDATE journal_lines j SET business_unit_id=l.business_unit_id FROM locations l WHERE j.location_id=l.id")
    op.execute("UPDATE journal_entries e SET business_unit_id=x.business_unit_id, location_id=x.location_id, department_id=x.department_id FROM (SELECT journal_entry_id,min(business_unit_id) business_unit_id,min(location_id) location_id,min(department_id) department_id FROM journal_lines GROUP BY journal_entry_id) x WHERE e.id=x.journal_entry_id")
    op.execute("UPDATE budget_lines b SET business_unit_id=u.id FROM business_units u WHERE upper(b.business_unit)=u.code")


def downgrade():
    dimensions = {
        "budget_lines": ["business_unit_id"],
        "bank_reconciliations": ["department_id", "location_id", "business_unit_id"],
        "journal_lines": ["business_unit_id"],
        "journal_entries": ["department_id", "location_id", "business_unit_id"],
        "goods_receipts": ["department_id", "location_id", "business_unit_id"],
        "payments": ["department_id", "location_id", "business_unit_id"],
        "supplier_invoices": ["business_unit_id"],
        "purchase_orders": ["business_unit_id"],
        "purchase_requisitions": ["business_unit_id"],
    }
    for table, columns in dimensions.items():
        for column in columns:
            op.drop_index(f"ix_{table}_{column}", table_name=table)
            op.drop_column(table, column)
    for column in ("default_department_id", "default_location_id", "default_business_unit_id"):
        op.drop_index(f"ix_users_{column}", table_name="users")
        op.drop_column("users", column)
