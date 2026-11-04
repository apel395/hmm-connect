"""Catering location defaults and invoice snapshots; no historical value changes."""
from alembic import op
import sqlalchemy as sa
revision = "20261104_catering_billing"
down_revision = "20261104_catering_prices"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("catering_location_billing",
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("configuration", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False))
    op.add_column("sales_transactions", sa.Column("billing_details", sa.JSON(), nullable=True))
    for col in (sa.Column("description", sa.Text(), nullable=True),
                sa.Column("registration_number", sa.String(150), nullable=True),
                sa.Column("service_period_from", sa.Date(), nullable=True),
                sa.Column("service_period_to", sa.Date(), nullable=True)):
        op.add_column("sales_transaction_lines", col)


def downgrade():
    connection = op.get_bind()
    if connection.execute(sa.text("SELECT 1 FROM catering_location_billing LIMIT 1")).first() or connection.execute(sa.text("SELECT 1 FROM sales_transactions WHERE billing_details IS NOT NULL LIMIT 1")).first() or connection.execute(sa.text("SELECT 1 FROM sales_transaction_lines WHERE description IS NOT NULL OR registration_number IS NOT NULL OR service_period_from IS NOT NULL OR service_period_to IS NOT NULL LIMIT 1")).first():
        raise RuntimeError("Saved Catering settings/invoice details exist; downgrade would discard them")
    for name in ("description", "registration_number", "service_period_from", "service_period_to"):
        op.drop_column("sales_transaction_lines", name)
    op.drop_column("sales_transactions", "billing_details")
    op.drop_table("catering_location_billing")
