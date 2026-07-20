"""add location and audit identity context

Revision ID: 20260720_identity_context
Revises: 20260720_procurement_accounting
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260720_identity_context"
down_revision: Union[str, Sequence[str], None] = "20260720_procurement_accounting"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "locations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(30), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("location_type", sa.String(30), nullable=False, server_default="OFFICE"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code", name="uq_locations_code"),
        sa.UniqueConstraint("name", name="uq_locations_name"),
    )

    op.add_column("users", sa.Column("location_id", sa.Integer(), nullable=True))
    op.create_index("ix_users_location_id", "users", ["location_id"])
    op.create_foreign_key(
        "fk_users_location_id",
        "users",
        "locations",
        ["location_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("audit_logs", sa.Column("actor_name", sa.String(150), nullable=True))
    op.add_column("audit_logs", sa.Column("department_id", sa.Integer(), nullable=True))
    op.add_column("audit_logs", sa.Column("department_name", sa.String(100), nullable=True))
    op.add_column("audit_logs", sa.Column("location_id", sa.Integer(), nullable=True))
    op.add_column("audit_logs", sa.Column("location_name", sa.String(120), nullable=True))
    op.add_column("audit_logs", sa.Column("role_names", sa.JSON(), nullable=True))
    op.create_index("ix_audit_logs_department_id", "audit_logs", ["department_id"])
    op.create_index("ix_audit_logs_location_id", "audit_logs", ["location_id"])

    op.execute(
        sa.text(
            """
            INSERT INTO locations (code, name, location_type)
            VALUES
                ('JKT', 'Jakarta Office', 'OFFICE'),
                ('SBY', 'Surabaya Office', 'OFFICE'),
                ('WH-JKT', 'Jakarta Warehouse', 'WAREHOUSE')
            ON CONFLICT DO NOTHING
            """
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO roles (name, description)
            VALUES
                ('ADMIN', 'System administrator'),
                ('PURCHASING', 'Purchasing operations'),
                ('FINANCE', 'Finance operations'),
                ('WAREHOUSE', 'Warehouse operations')
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    op.drop_index("ix_audit_logs_location_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_department_id", table_name="audit_logs")
    op.drop_column("audit_logs", "role_names")
    op.drop_column("audit_logs", "location_name")
    op.drop_column("audit_logs", "location_id")
    op.drop_column("audit_logs", "department_name")
    op.drop_column("audit_logs", "department_id")
    op.drop_column("audit_logs", "actor_name")
    op.drop_constraint("fk_users_location_id", "users", type_="foreignkey")
    op.drop_index("ix_users_location_id", table_name="users")
    op.drop_column("users", "location_id")
    op.drop_table("locations")
