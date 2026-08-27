"""Correct deterministic finance scope configuration.

Revision ID: 20260827_finance_posting_scope_integrity
Revises: 20260827_standard_operational_roles
"""

from alembic import op


revision = "20260827_finance_posting_scope_integrity"
down_revision = "20260827_standard_operational_roles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Rules using Hotel inventory/AP control accounts are Hotel rules, not
    # globally valid fallbacks for Project Catering locations.
    op.execute(
        """
        UPDATE accounting_posting_rules AS rule
        SET business_unit_id = bu.id
        FROM business_units AS bu,
             chart_of_accounts AS credit
        WHERE lower(bu.name) = 'hotel'
          AND credit.id = rule.credit_account_id
          AND credit.account_number = '200-100-1'
          AND rule.event_type IN (
              'SUPPLIER_INVOICE_INVENTORY',
              'SUPPLIER_INVOICE_DIRECT_USE'
          )
          AND rule.business_unit_id IS NULL
          AND rule.location_id IS NULL
        """
    )
    op.execute(
        """
        UPDATE accounting_posting_rules AS rule
        SET business_unit_id = bu.id
        FROM business_units AS bu,
             chart_of_accounts AS debit
        WHERE lower(bu.name) = 'hotel'
          AND debit.id = rule.debit_account_id
          AND debit.account_number = '200-100-1'
          AND rule.event_type = 'SUPPLIER_PAYMENT'
          AND rule.business_unit_id IS NULL
          AND rule.location_id IS NULL
        """
    )

    # The payment-rule credit account is only a validation/template account;
    # actual payment credit is resolved dynamically from BankAccount.coa_account_id.
    # Keep the Hotel template internally consistent when the known Hotel Mandiri
    # posting account exists.
    op.execute(
        """
        UPDATE accounting_posting_rules AS rule
        SET credit_account_id = hotel_bank.id
        FROM chart_of_accounts AS debit,
             chart_of_accounts AS hotel_bank,
             business_units AS bu
        WHERE debit.id = rule.debit_account_id
          AND debit.account_number = '200-100-1'
          AND hotel_bank.account_number = '100-110-110'
          AND lower(bu.name) = 'hotel'
          AND rule.business_unit_id = bu.id
          AND rule.event_type = 'SUPPLIER_PAYMENT'
        """
    )

    # Only assign bank-account locations where the account name itself is
    # deterministic and the target location resolves uniquely.
    op.execute(
        """
        DO $$
        DECLARE target_id integer;
        BEGIN
            SELECT min(id) INTO target_id
            FROM locations
            WHERE lower(name) LIKE '%zamp%'
               OR lower(code) LIKE '%zamp%';
            IF target_id IS NOT NULL
               AND (SELECT count(*) FROM locations
                    WHERE lower(name) LIKE '%zamp%'
                       OR lower(code) LIKE '%zamp%') = 1 THEN
                UPDATE bank_accounts
                SET location_id = target_id
                WHERE account_number = '100-100-102'
                  AND location_id IS NULL;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE target_id integer;
        BEGIN
            SELECT min(id) INTO target_id
            FROM locations
            WHERE lower(name) LIKE '%batam%'
               OR lower(code) LIKE '%batam%';
            IF target_id IS NOT NULL
               AND (SELECT count(*) FROM locations
                    WHERE lower(name) LIKE '%batam%'
                       OR lower(code) LIKE '%batam%') = 1 THEN
                UPDATE bank_accounts
                SET location_id = target_id
                WHERE account_number = '100-100-108'
                  AND location_id IS NULL;
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        DO $$
        DECLARE target_id integer;
        BEGIN
            SELECT min(id) INTO target_id
            FROM locations
            WHERE lower(name) LIKE '%duri%'
               OR lower(code) LIKE '%duri%';
            IF target_id IS NOT NULL
               AND (SELECT count(*) FROM locations
                    WHERE lower(name) LIKE '%duri%'
                       OR lower(code) LIKE '%duri%') = 1 THEN
                UPDATE bank_accounts
                SET location_id = target_id
                WHERE account_number = '100-100-109'
                  AND location_id IS NULL;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    # These changes repair live business configuration. Downgrade intentionally
    # does not re-globalize rules/accounts.
    pass
