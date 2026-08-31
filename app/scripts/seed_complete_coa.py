"""Ensure the complete approved Chart of Accounts is present in the database.

The canonical COA payload already lives in ``app.seeds.chart_of_accounts``.
This command intentionally reuses that idempotent seed instead of maintaining
another copy of the 302-account payload.

Usage:
    python -m app.scripts.seed_complete_coa
"""

from __future__ import annotations

from app.core.database import SessionLocal
from app.seeds import seed_database


def main() -> None:
    db = SessionLocal()
    try:
        seed_database(db)
        db.commit()
        print("Complete Chart of Accounts seed applied successfully.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
