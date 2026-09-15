"""Consolidate location-specific and exact-duplicate COAs.

Revision ID: 20260915_coa_cleanup
Revises: 20260915_ap_suspense_bridge

The accounting model uses journal/GL dimensions such as location_id instead of
creating one chart-of-account posting account for every outlet. Cash and bank
accounts are deliberately excluded because they represent distinct cash/bank
instruments.

The newly introduced AP Suspense account 200-100-999 is deliberately preserved.
"""

from alembic import op
import sqlalchemy as sa

revision = "20260915_coa_cleanup"
down_revision = "20260915_ap_suspense_bridge"
branch_labels = None
depends_on = None

# Location-specific COAs are replaced by a single canonical posting account.
# Cash and bank accounts are intentionally excluded.
# 200-100-999 AP Suspense is intentionally excluded because it was added by
# the immediately preceding migration and is a required system bridge account.
ACCOUNT_MAPPINGS = [
    # Petty cash -> one COA; location is carried on journal/GL lines.
    ("100-100-101", "100-100-100"),
    ("100-100-102", "100-100-100"),
    ("100-100-103", "100-100-100"),
    ("100-100-104", "100-100-100"),
    ("100-100-105", "100-100-100"),
    ("100-100-106", "100-100-100"),
    ("100-100-107", "100-100-100"),
    ("100-100-108", "100-100-100"),
    ("100-100-109", "100-100-100"),
    ("100-100-110", "100-100-100"),
    ("100-100-111", "100-100-100"),
    ("100-100-112", "100-100-100"),
    ("100-100-990", "100-100-100"),

    # AR -> one common trade receivable account.
    ("100-200-102", "100-200-101"),
    ("100-200-103", "100-200-101"),
    ("100-200-104", "100-200-101"),
    ("100-200-105", "100-200-101"),
    ("100-200-106", "100-200-101"),
    ("100-200-107", "100-200-101"),
    ("100-200-108", "100-200-101"),
    ("100-200-109", "100-200-101"),
    ("100-200-110", "100-200-101"),
    ("100-200-111", "100-200-101"),

    # Inventory -> one account per inventory class; location is carried on
    # journal/GL/inventory rows rather than encoded in the COA.
    ("100-300-101", "100-300-100"),
    ("100-300-102", "100-300-100"),
    ("100-300-103", "100-300-100"),
    ("100-300-104", "100-300-100"),
    ("100-300-105", "100-300-100"),
    ("100-300-106", "100-300-100"),
    ("100-300-107", "100-300-100"),
    ("100-300-108", "100-300-100"),
    ("100-300-109", "100-300-100"),
    ("100-300-501", "100-300-500"),
    ("100-300-502", "100-300-500"),
    ("100-300-503", "100-300-500"),
    ("100-300-504", "100-300-500"),
    ("100-300-505", "100-300-500"),
    ("100-300-506", "100-300-500"),
    ("100-300-507", "100-300-500"),
    ("100-300-508", "100-300-500"),
    ("100-300-509", "100-300-500"),
    ("100-300-701", "100-300-700"),
    ("100-300-702", "100-300-700"),
    ("100-300-703", "100-300-700"),
    ("100-300-704", "100-300-700"),
    ("100-300-705", "100-300-700"),
    ("100-300-706", "100-300-700"),
    ("100-300-707", "100-300-700"),
    ("100-300-708", "100-300-700"),
    ("100-300-709", "100-300-700"),

    # Trade AP -> one common supplier payable account.
    ("200-100-2", "200-100-1"),
    ("200-100-3", "200-100-1"),
    ("200-100-4", "200-100-1"),
    ("200-100-5", "200-100-1"),
    ("200-100-6", "200-100-1"),
    ("200-100-7", "200-100-1"),
    ("200-100-8", "200-100-1"),
    ("200-100-9", "200-100-1"),
    ("200-100-10", "200-100-1"),

    # Payroll accrual -> one common salary accrual account.
    ("200-200-101", "200-200-100"),
    ("200-200-102", "200-200-100"),
    ("200-200-103", "200-200-100"),
    ("200-200-104", "200-200-100"),
    ("200-200-105", "200-200-100"),
    ("200-200-106", "200-200-100"),
    ("200-200-107", "200-200-100"),
    ("200-200-108", "200-200-100"),
    ("200-200-109", "200-200-100"),

    # Exact duplicate posting accounts with identical accounting meaning.
    ("100-900-104", "100-900-103"),
    ("200-600-106", "200-600-100"),
]

CANONICAL_NAMES = {
    "100-100-100": "Petty Cash",
    "100-200-101": "Piutang Usaha",
    "100-300-100": "Inv Makanan",
    "100-300-500": "Inv Minuman",
    "100-300-700": "Inv Material",
    "200-100-1": "Hutang Usaha",
    "200-200-100": "Accrual Gaji",
}


def _remap_foreign_keys(bind, old_id: int, new_id: int) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT
                kcu.table_schema,
                kcu.table_name,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_schema = tc.constraint_schema
             AND kcu.constraint_name = tc.constraint_name
             AND kcu.table_schema = tc.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_schema = tc.constraint_schema
             AND ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_schema = 'public'
              AND ccu.table_name = 'chart_of_accounts'
              AND ccu.column_name = 'id'
              AND kcu.table_schema = 'public'
            ORDER BY kcu.table_schema, kcu.table_name, kcu.column_name
            """
        )
    ).mappings().all()

    for row in rows:
        table_schema = row["table_schema"]
        table_name = row["table_name"]
        column_name = row["column_name"]

        if table_name == "chart_of_accounts" and column_name == "id":
            continue

        qualified_table = (
            f'"{table_schema.replace(chr(34), chr(34) * 2)}".'
            f'"{table_name.replace(chr(34), chr(34) * 2)}"'
        )
        quoted_column = f'"{column_name.replace(chr(34), chr(34) * 2)}"'

        bind.execute(
            sa.text(
                f"UPDATE {qualified_table} "
                f"SET {quoted_column} = :new_id "
                f"WHERE {quoted_column} = :old_id"
            ),
            {"new_id": new_id, "old_id": old_id},
        )


def _assert_no_foreign_key_references(bind, account_id: int, account_code: str) -> None:
    rows = bind.execute(
        sa.text(
            """
            SELECT DISTINCT
                kcu.table_schema,
                kcu.table_name,
                kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON kcu.constraint_schema = tc.constraint_schema
             AND kcu.constraint_name = tc.constraint_name
             AND kcu.table_schema = tc.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_schema = tc.constraint_schema
             AND ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND ccu.table_schema = 'public'
              AND ccu.table_name = 'chart_of_accounts'
              AND ccu.column_name = 'id'
              AND kcu.table_schema = 'public'
            ORDER BY kcu.table_schema, kcu.table_name, kcu.column_name
            """
        )
    ).mappings().all()

    for row in rows:
        table_schema = row["table_schema"]
        table_name = row["table_name"]
        column_name = row["column_name"]

        if table_name == "chart_of_accounts" and column_name == "id":
            continue

        qualified_table = (
            f'"{table_schema.replace(chr(34), chr(34) * 2)}".'
            f'"{table_name.replace(chr(34), chr(34) * 2)}"'
        )
        quoted_column = f'"{column_name.replace(chr(34), chr(34) * 2)}"'

        count = bind.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {qualified_table} "
                f"WHERE {quoted_column} = :account_id"
            ),
            {"account_id": account_id},
        ).scalar_one()

        if count:
            raise RuntimeError(
                f"COA {account_code} is still referenced by "
                f"{table_schema}.{table_name}.{column_name} ({count} rows)."
            )


def upgrade() -> None:
    bind = op.get_bind()

    suspense = bind.execute(
        sa.text(
            "SELECT id FROM chart_of_accounts WHERE account_number = '200-100-999'"
        )
    ).scalar_one_or_none()
    if suspense is None:
        raise RuntimeError(
            "Required AP Suspense account 200-100-999 is missing; "
            "COA cleanup will not proceed."
        )

    # Multiple operational petty-cash records may intentionally share the
    # consolidated 100-100-100 GL account. The old bank_accounts schema made
    # coa_account_id globally unique, which encoded the old location-specific
    # COA design and prevents this consolidation. Bank accounts themselves are
    # still distinct by bank_name + account_number.
    bind.execute(
        sa.text(
            "ALTER TABLE public.bank_accounts "
            "DROP CONSTRAINT IF EXISTS uq_bank_account_coa"
        )
    )

    for old_code, canonical_code in ACCOUNT_MAPPINGS:
        old_id = bind.execute(
            sa.text(
                "SELECT id FROM chart_of_accounts WHERE account_number = :code"
            ),
            {"code": old_code},
        ).scalar_one_or_none()
        canonical_id = bind.execute(
            sa.text(
                "SELECT id FROM chart_of_accounts WHERE account_number = :code"
            ),
            {"code": canonical_code},
        ).scalar_one_or_none()

        if old_id is None:
            continue
        if canonical_id is None:
            raise RuntimeError(
                f"Canonical COA {canonical_code} is missing; cannot merge {old_code}."
            )
        if old_id == canonical_id:
            continue

        _remap_foreign_keys(bind, old_id, canonical_id)
        _assert_no_foreign_key_references(bind, old_id, old_code)

        bind.execute(
            sa.text("DELETE FROM chart_of_accounts WHERE id = :id"),
            {"id": old_id},
        )

    for code, name in CANONICAL_NAMES.items():
        bind.execute(
            sa.text(
                "UPDATE chart_of_accounts "
                "SET account_name = :name "
                "WHERE account_number = :code"
            ),
            {"name": name, "code": code},
        )


def downgrade() -> None:
    raise RuntimeError(
        "20260915_coa_cleanup is intentionally irreversible because it consolidates "
        "historical COA references into canonical accounts."
    )
