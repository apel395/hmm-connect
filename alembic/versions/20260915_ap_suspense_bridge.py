"""Add AP suspense bridge for Receiving -> Supplier Invoice.

Revision ID: 20260915_ap_suspense_bridge
Revises: 20260912_item_type_buy_sell
"""

from alembic import op
import sqlalchemy as sa

revision = "20260915_ap_suspense_bridge"
down_revision = "20260912_item_type_buy_sell"
branch_labels = None
depends_on = None


AP_SUSPENSE_CODE = "200-100-999"
AP_SUSPENSE_NAME = "AP Suspense Account"
AP_SUSPENSE_SETTING = "AP_SUSPENSE_ACCOUNT"
LEGACY_GRNI_SETTING = "GRNI_ACCOUNT"


def upgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            """
            INSERT INTO chart_of_accounts (
                account_number,
                account_name,
                account_type,
                normal_balance,
                description,
                account_subtype,
                financial_statement_group,
                is_posting,
                is_system,
                is_active
            )
            VALUES (
                :code,
                :name,
                'LIABILITY',
                'CREDIT',
                :description,
                'OTHER',
                'BALANCE_SHEET',
                TRUE,
                TRUE,
                TRUE
            )
            ON CONFLICT (account_number) DO UPDATE
            SET
                account_name = EXCLUDED.account_name,
                account_type = EXCLUDED.account_type,
                normal_balance = EXCLUDED.normal_balance,
                description = EXCLUDED.description,
                account_subtype = EXCLUDED.account_subtype,
                financial_statement_group = EXCLUDED.financial_statement_group,
                is_posting = TRUE,
                is_system = TRUE,
                is_active = TRUE
            """
        ).bindparams(
            code=AP_SUSPENSE_CODE,
            name=AP_SUSPENSE_NAME,
            description="Temporary liability bridge between Goods Receiving and Supplier Invoice.",
        )
    )

    account_id = bind.execute(
        sa.text(
            "SELECT id FROM chart_of_accounts WHERE account_number = :code"
        ).bindparams(code=AP_SUSPENSE_CODE)
    ).scalar_one()

    bind.execute(
        sa.text(
            """
            INSERT INTO accounting_settings (setting_key, account_id, description)
            VALUES (:setting_key, :account_id, :description)
            ON CONFLICT (setting_key) DO UPDATE
            SET account_id = EXCLUDED.account_id,
                description = EXCLUDED.description
            """
        ).bindparams(
            setting_key=AP_SUSPENSE_SETTING,
            account_id=account_id,
            description="Common Receiving -> Supplier Invoice AP suspense bridge.",
        )
    )

    # Keep the existing GRNI key compatible with the posting validator and
    # migrate it to the same bridge account. This also creates the key when a
    # legacy database never had an explicit GRNI setting.
    bind.execute(
        sa.text(
            """
            INSERT INTO accounting_settings (setting_key, account_id, description)
            VALUES (:setting_key, :account_id, :description)
            ON CONFLICT (setting_key) DO UPDATE
            SET account_id = EXCLUDED.account_id,
                description = EXCLUDED.description
            """
        ).bindparams(
            setting_key=LEGACY_GRNI_SETTING,
            account_id=account_id,
            description="Legacy GRNI key mapped to the AP Suspense bridge account.",
        )
    )


def downgrade() -> None:
    bind = op.get_bind()

    bind.execute(
        sa.text(
            "DELETE FROM accounting_settings WHERE setting_key = :setting_key"
        ).bindparams(setting_key=AP_SUSPENSE_SETTING)
    )

    # Do not delete the COA if it has already been used by journal history.
    used = bind.execute(
        sa.text(
            """
            SELECT EXISTS (
                SELECT 1
                FROM journal_lines jl
                JOIN chart_of_accounts coa ON coa.id = jl.account_id
                WHERE coa.account_number = :code
            )
            """
        ).bindparams(code=AP_SUSPENSE_CODE)
    ).scalar_one()

    if not used:
        bind.execute(
            sa.text(
                "DELETE FROM chart_of_accounts WHERE account_number = :code"
            ).bindparams(code=AP_SUSPENSE_CODE)
        )
