"""add_chart_of_account_fields

Revision ID: 1beabe691421
Revises: bbba00ffdf97
Create Date: 2026-07-23 09:44:58.739479

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "1beabe691421"
down_revision = "bbba00ffdf97"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "chart_of_accounts",
        sa.Column(
            "cash_flow_category",
            sa.String(length=30),
            nullable=True,
        ),
    )

    op.add_column(
        "chart_of_accounts",
        sa.Column(
            "parent_account_id",
            sa.Integer(),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_chart_of_accounts_parent",
        "chart_of_accounts",
        "chart_of_accounts",
        ["parent_account_id"],
        ["id"],
    )

    op.add_column(
        "chart_of_accounts",
        sa.Column(
            "is_posting",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )

    op.add_column(
        "chart_of_accounts",
        sa.Column(
            "is_system",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )


def downgrade():
    op.drop_constraint(
        "fk_chart_of_accounts_parent",
        "chart_of_accounts",
        type_="foreignkey",
    )

    op.drop_column(
        "chart_of_accounts",
        "is_system",
    )

    op.drop_column(
        "chart_of_accounts",
        "is_posting",
    )

    op.drop_column(
        "chart_of_accounts",
        "parent_account_id",
    )

    op.drop_column(
        "chart_of_accounts",
        "cash_flow_category",
    )