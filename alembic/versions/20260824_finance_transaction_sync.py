"""Repair legacy finance context and seed scoped supplier payment rules.

Revision ID: 20260824_finance_transaction_sync
Revises: 20260824_scoped_posting_rules
"""

from alembic import op


revision = "20260824_finance_transaction_sync"
down_revision = "20260824_scoped_posting_rules"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Repair invoice location inherited from the posted receiving chain.  This is
    # intentionally data-only: source documents remain the authoritative context.
    op.execute(
        """
        UPDATE supplier_invoices AS invoice
        SET location_id = source.location_id
        FROM (
            SELECT
                current_invoice.id AS invoice_id,
                COALESCE(
                    receipt.location_id,
                    warehouse.location_id,
                    purchase_order.location_id
                ) AS location_id
            FROM supplier_invoices AS current_invoice
            JOIN goods_receipts AS receipt
                ON receipt.id = current_invoice.goods_receipt_id
            LEFT JOIN warehouses AS warehouse
                ON warehouse.id = receipt.warehouse_id
            LEFT JOIN purchase_orders AS purchase_order
                ON purchase_order.id = COALESCE(
                    receipt.purchase_order_id,
                    current_invoice.purchase_order_id
                )
        ) AS source
        WHERE invoice.id = source.invoice_id
          AND invoice.location_id IS NULL
          AND source.location_id IS NOT NULL
        """
    )

    op.execute(
        """
        UPDATE supplier_invoices AS invoice
        SET location_id = purchase_order.location_id
        FROM purchase_orders AS purchase_order
        WHERE invoice.purchase_order_id = purchase_order.id
          AND invoice.location_id IS NULL
          AND purchase_order.location_id IS NOT NULL
        """
    )

    # A registered physical bank account is authoritative evidence that its
    # linked posting COA is a BANK account, including legacy imported COAs.
    op.execute(
        """
        UPDATE chart_of_accounts AS account
        SET account_subtype = 'BANK'
        WHERE account.id IN (
            SELECT bank.coa_account_id
            FROM bank_accounts AS bank
            WHERE bank.is_active IS TRUE
        )
          AND account.account_subtype <> 'BANK'
        """
    )

    # Derive a location-scoped payment rule from the corresponding invoice
    # liability control and the best matching registered funding account.
    op.execute(
        """
        WITH invoice_rules AS (
            SELECT DISTINCT ON (rule.business_unit_id, rule.location_id)
                rule.business_unit_id,
                rule.location_id,
                rule.credit_account_id AS payable_account_id
            FROM accounting_posting_rules AS rule
            WHERE rule.event_type IN (
                'SUPPLIER_INVOICE_INVENTORY',
                'SUPPLIER_INVOICE_DIRECT_USE'
            )
              AND rule.is_active IS TRUE
              AND rule.business_unit_id IS NOT NULL
              AND rule.location_id IS NOT NULL
            ORDER BY
                rule.business_unit_id,
                rule.location_id,
                rule.id DESC
        )
        INSERT INTO accounting_posting_rules (
            event_type,
            business_unit_id,
            location_id,
            debit_account_id,
            credit_account_id,
            description,
            is_active
        )
        SELECT
            'SUPPLIER_PAYMENT',
            source.business_unit_id,
            source.location_id,
            source.payable_account_id,
            funding.coa_account_id,
            'Auto-scoped supplier payment rule',
            TRUE
        FROM invoice_rules AS source
        JOIN LATERAL (
            SELECT bank.coa_account_id
            FROM bank_accounts AS bank
            WHERE bank.is_active IS TRUE
              AND bank.business_unit_id = source.business_unit_id
              AND (
                    bank.location_id = source.location_id
                    OR bank.location_id IS NULL
              )
            ORDER BY
                CASE WHEN bank.location_id = source.location_id THEN 0 ELSE 1 END,
                bank.id
            LIMIT 1
        ) AS funding ON TRUE
        WHERE NOT EXISTS (
            SELECT 1
            FROM accounting_posting_rules AS existing
            WHERE existing.event_type = 'SUPPLIER_PAYMENT'
              AND existing.is_active IS TRUE
              AND existing.business_unit_id = source.business_unit_id
              AND existing.location_id = source.location_id
        )
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM accounting_posting_rules
        WHERE event_type = 'SUPPLIER_PAYMENT'
          AND description = 'Auto-scoped supplier payment rule'
        """
    )
