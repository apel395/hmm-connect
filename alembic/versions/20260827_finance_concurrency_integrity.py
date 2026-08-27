"""Harden finance transaction concurrency invariants.

Revision ID: 20260827_finance_concurrency_integrity
Revises: 20260827_finance_location_backfill
"""

from alembic import op


revision = "20260827_finance_concurrency_integrity"
down_revision = "20260827_finance_location_backfill"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Financial history must never be silently merged. Fail clearly if legacy
    # duplicates exist so an administrator can reconcile them deliberately.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM supplier_invoices
                GROUP BY supplier_id, lower(btrim(supplier_invoice_number))
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot create supplier invoice uniqueness index: duplicate supplier invoice numbers exist';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_supplier_invoice_supplier_number_ci
        ON supplier_invoices (supplier_id, lower(btrim(supplier_invoice_number)))
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM account_payables
                WHERE invoice_number IS NOT NULL
                GROUP BY supplier_id, invoice_number
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot create AP source uniqueness index: duplicate supplier/invoice AP rows exist';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_account_payable_supplier_invoice_number
        ON account_payables (supplier_id, invoice_number)
        WHERE invoice_number IS NOT NULL
        """
    )

    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM journal_entries
                WHERE status <> 'VOID'
                  AND reference_type IN (
                      'SUPPLIER_INVOICE',
                      'SUPPLIER_PAYMENT',
                      'SUPPLIER_ADJUSTMENT',
                      'BANK_TRANSFER'
                  )
                GROUP BY reference_type, reference_id
                HAVING count(*) > 1
            ) THEN
                RAISE EXCEPTION
                    'Cannot create active source journal uniqueness index: duplicate active source journals exist';
            END IF;
        END $$;
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_journal_active_finance_source
        ON journal_entries (reference_type, reference_id)
        WHERE status <> 'VOID'
          AND reference_type IN (
              'SUPPLIER_INVOICE',
              'SUPPLIER_PAYMENT',
              'SUPPLIER_ADJUSTMENT',
              'BANK_TRANSFER'
          )
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_journal_active_finance_source")
    op.execute("DROP INDEX IF EXISTS uq_account_payable_supplier_invoice_number")
    op.execute("DROP INDEX IF EXISTS uq_supplier_invoice_supplier_number_ci")
