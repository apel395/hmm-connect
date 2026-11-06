"""Add deterministic Project Catering Duri posting rules.

Revision ID: 20260827_duri_posting_rules
Revises: 20260827_finance_posting_scope_integrity
"""

from alembic import op


revision = "20260827_duri_posting_rules"
down_revision = "20260827_finance_posting_scope_integrity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE
            bu_id integer;
            loc_id integer;
            inv_id integer;
            ap_id integer;
            vat_id integer;
            direct_use_id integer;
            cash_id integer;
        BEGIN
            SELECT id INTO bu_id
            FROM business_units
            WHERE lower(name) = 'project catering'
            LIMIT 1;

            SELECT id INTO loc_id
            FROM locations
            WHERE lower(name) = 'duri' OR code = 'SPHR0802A'
            ORDER BY CASE WHEN lower(name) = 'duri' THEN 0 ELSE 1 END
            LIMIT 1;

            SELECT id INTO inv_id
            FROM chart_of_accounts
            WHERE account_number = '100-300-107'
              AND is_active = true
              AND is_posting = true
            LIMIT 1;

            SELECT id INTO ap_id
            FROM chart_of_accounts
            WHERE account_number = '200-100-8'
              AND is_active = true
              AND is_posting = true
            LIMIT 1;

            SELECT id INTO vat_id
            FROM chart_of_accounts
            WHERE account_number = '100-500-100'
              AND is_active = true
              AND is_posting = true
            LIMIT 1;

            SELECT id INTO direct_use_id
            FROM chart_of_accounts
            WHERE account_number = '100-300-999'
              AND is_active = true
              AND is_posting = true
            LIMIT 1;

            SELECT id INTO cash_id
            FROM chart_of_accounts
            WHERE account_number = '100-100-109'
              AND is_active = true
              AND is_posting = true
            LIMIT 1;

            IF bu_id IS NULL OR loc_id IS NULL THEN
                RAISE EXCEPTION 'Duri Project Catering business/location could not be resolved';
            END IF;
            IF inv_id IS NULL OR ap_id IS NULL OR vat_id IS NULL OR direct_use_id IS NULL OR cash_id IS NULL THEN
                RAISE EXCEPTION 'Required Duri finance COA is missing';
            END IF;

            DELETE FROM accounting_posting_rules
            WHERE business_unit_id = bu_id
              AND location_id = loc_id
              AND event_type IN (
                  'SUPPLIER_INVOICE_INVENTORY',
                  'SUPPLIER_INVOICE_DIRECT_USE',
                  'SUPPLIER_PAYMENT'
              );

            INSERT INTO accounting_posting_rules (
                event_type,
                business_unit_id,
                location_id,
                debit_account_id,
                credit_account_id,
                input_vat_account_id,
                description,
                is_active,
                created_by_id,
                created_at,
                updated_at
            )
            VALUES
                (
                    'SUPPLIER_INVOICE_INVENTORY',
                    bu_id,
                    loc_id,
                    inv_id,
                    ap_id,
                    vat_id,
                    'Duri inventory supplier invoice: inventory / AP / input VAT',
                    true,
                    NULL,
                    now(),
                    now()
                ),
                (
                    'SUPPLIER_INVOICE_DIRECT_USE',
                    bu_id,
                    loc_id,
                    direct_use_id,
                    ap_id,
                    vat_id,
                    'Duri direct-use supplier invoice: approved temporary inventory fallback / AP / input VAT',
                    true,
                    NULL,
                    now(),
                    now()
                ),
                (
                    'SUPPLIER_PAYMENT',
                    bu_id,
                    loc_id,
                    ap_id,
                    cash_id,
                    NULL,
                    'Duri supplier payment: AP / dynamic selected funding account',
                    true,
                    NULL,
                    now(),
                    now()
                );
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM accounting_posting_rules
        WHERE business_unit_id = (
            SELECT id FROM business_units WHERE lower(name) = 'project catering' LIMIT 1
        )
          AND location_id = (
            SELECT id FROM locations
            WHERE lower(name) = 'duri' OR code = 'SPHR0802A'
            ORDER BY CASE WHEN lower(name) = 'duri' THEN 0 ELSE 1 END
            LIMIT 1
        )
          AND event_type IN (
              'SUPPLIER_INVOICE_INVENTORY',
              'SUPPLIER_INVOICE_DIRECT_USE',
              'SUPPLIER_PAYMENT'
          );
        """
    )
