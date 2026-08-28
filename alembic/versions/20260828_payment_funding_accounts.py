"""Classify bank accounts eligible for supplier-payment funding.

Revision ID: 20260828_payment_funding_accounts
Revises: 20260828_seed_direct_coa_xls
"""

from alembic import op
import sqlalchemy as sa


revision = "20260828_payment_funding_accounts"
down_revision = "20260828_seed_direct_coa_xls"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "bank_accounts",
        sa.Column("is_payment_account", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Finance-approved payment accounts. Compare normalized account numbers so
    # formatting differences such as hyphens/dots/spaces do not matter.
    op.execute(
        """
        UPDATE bank_accounts
        SET is_payment_account = (
            regexp_replace(account_number, '[^0-9]', '', 'g') IN (
                '1080025915225',
                '1080070025250',
                '1080079252525'
            )
        )
        """
    )

    # Explicit holding/collection accounts from Finance remain non-payment.
    op.execute(
        """
        UPDATE bank_accounts
        SET is_payment_account = false
        WHERE regexp_replace(account_number, '[^0-9]', '', 'g') IN (
            '1080012525250',
            '1080053252525',
            '7003724667',
            '107901000207301',
            '1003488221'
        )
        """
    )

    op.alter_column("bank_accounts", "is_payment_account", server_default=None)
    op.create_index(
        "ix_bank_accounts_is_payment_account",
        "bank_accounts",
        ["is_payment_account"],
    )


def downgrade() -> None:
    op.drop_index("ix_bank_accounts_is_payment_account", table_name="bank_accounts")
    op.drop_column("bank_accounts", "is_payment_account")
