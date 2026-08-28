"""Add SYRUP subgroup under Beverage.

Revision ID: 20260828_beverage_syrup
Revises: 20260828_payment_funding_accounts
"""

from alembic import op


revision = "20260828_beverage_syrup"
down_revision = "20260828_payment_funding_accounts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            beverage_group_id integer;
            beverage_count integer;
        BEGIN
            SELECT count(*), min(id)
            INTO beverage_count, beverage_group_id
            FROM item_groups
            WHERE is_active = true
              AND lower(trim(name)) IN ('beverage', 'beverages', 'minuman');

            IF beverage_count <> 1 THEN
                RAISE EXCEPTION
                    'SYRUP seed requires exactly one active Beverage/Minuman item group; found %',
                    beverage_count;
            END IF;

            INSERT INTO item_subgroups (
                code,
                name,
                group_id,
                is_active,
                created_at,
                updated_at
            )
            VALUES (
                'SYRUP',
                'SYRUP',
                beverage_group_id,
                true,
                now(),
                now()
            )
            ON CONFLICT (code)
            DO UPDATE SET
                name = EXCLUDED.name,
                group_id = EXCLUDED.group_id,
                is_active = true,
                updated_at = now();
        END $$;
        """
    )


def downgrade() -> None:
    UPDATE_SQL = """
        UPDATE item_subgroups
        SET is_active = false,
            updated_at = now()
        WHERE code = 'SYRUP'
          AND upper(trim(name)) = 'SYRUP'
    """
    op.execute(UPDATE_SQL)
