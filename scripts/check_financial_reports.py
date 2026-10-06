"""Read-only EC2 check for financial report schema, responses and closing setup."""
import argparse
import json
import sys
from datetime import datetime, date
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.encoders import jsonable_encoder
from sqlalchemy import inspect, text
from app.core.database import SessionLocal
from app.api.v1.profit_loss import serialize
from app.services.financial_reporting_service import FinancialReportingService
from app.services.period_closing_service import PeriodClosingService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, default=datetime.now(ZoneInfo("Asia/Jakarta")).date())
    parser.add_argument("--location-id", type=int)
    args = parser.parse_args()
    failed = False
    with SessionLocal() as db:
        if db.get_bind().dialect.name == "postgresql":
            db.execute(text("SET TRANSACTION READ ONLY"))
        schema = inspect(db.connection())
        revisions = db.execute(text("SELECT version_num FROM alembic_version")).scalars().all() if schema.has_table("alembic_version") else []
        print("Migration:", revisions)
        prerequisites = {
            "financial_report_settings": schema.has_table("financial_report_settings"),
            "fiscal_periods.closing_journal_ids": schema.has_table("fiscal_periods") and "closing_journal_ids" in {c["name"] for c in schema.get_columns("fiscal_periods")},
            "budgets": schema.has_table("budgets"),
            "budget_lines": schema.has_table("budget_lines"),
        }
        print("Schema:", json.dumps(prerequisites))
        if not all(prerequisites.values()):
            failed = True
            print("Database update required: .venv/bin/alembic upgrade head")
        # A savepoint keeps an unexpected SQL failure from preventing the next
        # independent check. The entire transaction is rolled back on exit.
        for kind in ("BALANCE_SHEET", "PROFIT_LOSS"):
            try:
                with db.begin_nested():
                    report = FinancialReportingService(db).build(report_type=kind,
                        as_of_date=args.date, location_id=args.location_id)
                    payload = jsonable_encoder(serialize(report))
                    json.dumps(payload, allow_nan=False)
                    print(kind, "OK", "rows:", len(payload["rows"]), "location:", args.location_id)
                    print("Totals:", json.dumps(payload["section_totals"], ensure_ascii=False))
            except Exception as exc:
                failed = True
                print(kind, "FAILED", type(exc).__name__)
                # SQLAlchemy exceptions can include connection parameters. Keep
                # only the DB's error text, without SQL or bound parameters.
                cause = getattr(exc, "orig", None)
                print(str(cause) if cause else getattr(exc, "detail", str(exc)))
        try:
            with db.begin_nested():
                account = PeriodClosingService.earnings_account(db)
                print("Closing earnings account:", account.account_number, account.account_name)
        except Exception as exc:
            failed = True
            print("Closing setup FAILED:", getattr(exc, "detail", type(exc).__name__))
        db.rollback()
    print("READ ONLY: no balances, budgets, journals or periods changed.")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
