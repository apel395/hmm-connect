"""Seed purchasing approval roles from the approved business workflow.

Revision ID: 20260814_purchasing_approval_roles
Revises: 20260814_item_level_ppn
"""
from alembic import op
import sqlalchemy as sa

revision = "20260814_purchasing_approval_roles"
down_revision = "20260814_item_level_ppn"
branch_labels = None
depends_on = None

ROLES = (
    ("STORE", "Location store approval for PR and receiving"),
    ("CHEF", "Location chef approval for PR and receiving"),
    ("PM/CAMP BOSS", "Location PM or Camp Boss approval for PR and receiving"),
    ("HO PURCHASING", "Head Office purchasing approval"),
    ("FINANCE", "Finance approval after Head Office purchasing"),
    ("GENERAL MANAGER", "General Manager final approval"),
)


def upgrade():
    # Alembic creates this column as VARCHAR(32), while this and later descriptive
    # revision identifiers are longer than 32 characters.
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=255),
        existing_nullable=False,
    )
    connection = op.get_bind()
    roles = sa.table(
        "roles",
        sa.column("name", sa.String(50)),
        sa.column("description", sa.String(200)),
    )
    for name, description in ROLES:
        exists = connection.execute(
            sa.text("SELECT 1 FROM roles WHERE UPPER(name) = UPPER(:name) LIMIT 1"),
            {"name": name},
        ).first()
        if not exists:
            connection.execute(roles.insert().values(name=name, description=description))


def downgrade():
    pass
