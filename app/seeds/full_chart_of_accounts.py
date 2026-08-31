from __future__ import annotations

import base64
import gzip
import json

from sqlalchemy.orm import Session

from app.models.chart_of_account import ChartOfAccount


# Source: COA.xlsx supplied for the hotel chart of accounts.
# 302 unique account codes are embedded so the seed is self-contained and does
# not require pandas/openpyxl in the Lambda/API runtime.
_COA_PAYLOAD_GZIP_B64 = """__PAYLOAD__"""


def seed_full_chart_of_accounts(db: Session) -> int:
    """Import missing COA rows without overwriting existing production rows.

    The import is idempotent and resolves parent accounts by account number.
    Existing COA records are intentionally left untouched because transaction
    rows may already reference them.
    """
    rows = json.loads(
        gzip.decompress(base64.b64decode(_COA_PAYLOAD_GZIP_B64)).decode("utf-8")
    )

    existing = {
        account.account_number: account
        for account in db.query(ChartOfAccount).all()
    }

    # Parents must exist before children so parent_account_id can be resolved
    # without relying on database-generated IDs from a second transaction.
    rows = sorted(rows, key=lambda row: (row["account_number"].count("-"), row["account_number"]))
    created = 0

    for row in rows:
        account_number = row["account_number"]
        if account_number in existing:
            continue

        parent = existing.get(row.get("parent_account_number"))
        account = ChartOfAccount(
            account_number=account_number,
            account_name=row["account_name"],
            account_type=row["account_type"],
            normal_balance=row["normal_balance"],
            description=row.get("description"),
            cash_flow_category=row.get("cash_flow_category"),
            account_subtype=row.get("account_subtype") or "OTHER",
            financial_statement_group=row.get("financial_statement_group"),
            parent_account_id=parent.id if parent else None,
            is_posting=bool(row.get("is_posting", True)),
            is_system=bool(row.get("is_system", False)),
            is_active=bool(row.get("is_active", True)),
        )
        db.add(account)
        db.flush()
        existing[account_number] = account
        created += 1

    if created:
        db.commit()

    return created
