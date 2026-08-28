"""Activate deterministic direct COA mappings needed by supplier invoice verification.

Revision ID: 20260828_activate_direct_coa
Revises: 20260828_location_repair_v2

This seed intentionally maps only accounts that are unambiguous in the approved
COA workbook:
- Input VAT -> 100-500-100 Pajak Ppn Masukan
- Supplier PR0014 (AIR MINERAL DC) payable -> 200-100-7 Hutang Usaha - MC Dellmott

No journal rows are changed.
"""

from alembic import op


revision = "20260828_activate_direct_coa"
down_revision = "20260828_location_repair_v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            vat_id integer;
            ap_batam_id integer;
            supplier_id integer;
        BEGIN
            SELECT id INTO vat_id
            FROM chart_of_accounts
            WHERE account_number = '100-500-100'
              AND is_active = true
              AND is_posting = true
              AND account_type = 'ASSET'
              AND normal_balance = 'DEBIT'
            LIMIT 1;

            IF vat_id IS NULL THEN
                RAISE EXCEPTION
                    'Direct COA seed aborted: active posting Input VAT account 100-500-100 was not found';
            END IF;

            SELECT id INTO ap_batam_id
            FROM chart_of_accounts
            WHERE account_number = '200-100-7'
              AND is_active = true
              AND is_posting = true
              AND account_type = 'LIABILITY'
              AND normal_balance = 'CREDIT'
            LIMIT 1;

            IF ap_batam_id IS NULL THEN
                RAISE EXCEPTION
                    'Direct COA seed aborted: active posting Batam AP account 200-100-7 was not found';
            END IF;

            SELECT id INTO supplier_id
            FROM suppliers
            WHERE code = 'PR0014'
            LIMIT 1;

            IF supplier_id IS NULL THEN
                RAISE EXCEPTION
                    'Direct COA seed aborted: supplier PR0014 was not found';
            END IF;

            UPDATE suppliers
            SET payable_account_id = ap_batam_id
            WHERE id = supplier_id;

            INSERT INTO accounting_settings (
                setting_key,
                account_id,
                description
            )
            VALUES (
                'INPUT_VAT_ACCOUNT',
                vat_id,
                'Direct COA for supplier-invoice input VAT'
            )
            ON CONFLICT (setting_key)
            DO UPDATE SET
                account_id = EXCLUDED.account_id,
                description = EXCLUDED.description;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            vat_id integer;
            ap_batam_id integer;
        BEGIN
            SELECT id INTO vat_id
            FROM chart_of_accounts
            WHERE account_number = '100-500-100'
            LIMIT 1;

            SELECT id INTO ap_batam_id
            FROM chart_of_accounts
            WHERE account_number = '200-100-7'
            LIMIT 1;

            UPDATE suppliers
            SET payable_account_id = NULL
            WHERE code = 'PR0014'
              AND payable_account_id = ap_batam_id;

            DELETE FROM accounting_settings
            WHERE setting_key = 'INPUT_VAT_ACCOUNT'
              AND account_id = vat_id
              AND description = 'Direct COA for supplier-invoice input VAT';
        END $$;
        """
    )
