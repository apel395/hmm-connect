"""create payments table"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "b43067e8ad3e"
down_revision = "1beabe691421"
branch_labels = None
depends_on = None


def upgrade():

    op.create_table(
        "payments",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True,
        ),

        sa.Column(
            "payment_number",
            sa.String(50),
            nullable=False,
        ),

        sa.Column(
            "account_payable_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "payment_date",
            sa.Date(),
            nullable=False,
        ),

        sa.Column(
            "amount",
            sa.Numeric(18, 2),
            nullable=False,
        ),

        sa.Column(
            "payment_method",
            sa.String(50),
            nullable=False,
        ),

        sa.Column(
            "reference_number",
            sa.String(100),
            nullable=True,
        ),

        sa.Column(
            "status",
            sa.String(30),
            nullable=False,
            server_default="PAID",
        ),

        sa.Column(
            "created_by_id",
            sa.Integer(),
            nullable=False,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),

        sa.ForeignKeyConstraint(
            ["account_payable_id"],
            ["account_payables.id"],
        ),

        sa.ForeignKeyConstraint(
            ["created_by_id"],
            ["users.id"],
        ),

        sa.UniqueConstraint(
            "payment_number",
        ),
    )

    op.create_index(
        "ix_payments_payment_number",
        "payments",
        ["payment_number"],
    )


def downgrade():

    op.drop_index(
        "ix_payments_payment_number",
        table_name="payments",
    )

    op.drop_table("payments")