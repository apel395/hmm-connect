#!/usr/bin/env python3
"""Seed Pak Ardi COA, Petty Cash accounts, and PPN Masukan mapping.

Dry-run:
    PYTHONPATH=. python scripts/seed_pak_ardi_coa_cash.py

Apply:
    PYTHONPATH=. python scripts/seed_pak_ardi_coa_cash.py --apply
"""

from __future__ import annotations

import argparse

from app.core.database import SessionLocal
from app.seeds.chart_of_accounts import (
    seed_cash_accounts,
    seed_chart_of_accounts,
    seed_input_vat_posting,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Commit changes; default is dry-run rollback")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        coa = seed_chart_of_accounts(db)
        cash = seed_cash_accounts(db)
        vat = seed_input_vat_posting(db)

        print("Pak Ardi finance seed summary:")
        print(f"  source_coa={coa['source']}")
        print(f"  coa_created={coa['created']}")
        print(f"  coa_existing_untouched={coa['existing_untouched']}")
        print(f"  cash_created={cash['created']}")
        print(f"  cash_existing_untouched={cash['existing_untouched']}")
        print(f"  input_vat_rules_configured={vat['configured']}")

        unresolved = cash.get("unresolved") or []
        if unresolved:
            print("  cash_unresolved:")
            for item in unresolved:
                print(f"    - {item}")

        missing = vat.get("missing") or []
        if missing:
            print("  input_vat_missing:")
            for item in missing:
                print(f"    - {item}")

        if args.apply:
            db.commit()
            print("Seed committed successfully.")
        else:
            db.rollback()
            print("Dry-run only; transaction rolled back. Use --apply to commit.")
        return 0
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
