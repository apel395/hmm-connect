"""Read-only EC2 verification after the 10-07 finance migration."""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from app.core.database import engine
from app.services.management_dashboard import build_dashboard
from app.api.v1.profit_loss import serialize


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--month", type=int, default=date.today().month)
    parser.add_argument("--location-id", type=int)
    args = parser.parse_args()
    with engine.connect() as connection, connection.begin():
        connection.execute(text("SET TRANSACTION READ ONLY"))
        schema = inspect(connection)
        required = {"products": {"service_charge_rate"}, "sales_transactions": {"service_charge_amount"},
            "sales_transaction_lines": {"service_charge_rate", "service_charge_amount"},
            "payments": {"bank_charge_amount", "short_over_amount", "bank_charge_account_id", "short_over_account_id", "difference_reason"},
            "ar_invoice_layouts": {"customer_id", "configuration"}}
        for table, columns in required.items():
            if not schema.has_table(table):
                raise SystemExit(f"Migration required: table {table} missing")
            missing = columns - {c["name"] for c in schema.get_columns(table)}
            if missing:
                raise SystemExit(f"Migration required: {table} missing {sorted(missing)}")
        with Session(bind=connection) as db:
            report = serialize(build_dashboard(db, year=args.year, month=args.month, location_id=args.location_id))
            print(json.dumps({"schema": "OK", "as_of_date": report["as_of_date"], "scope": report["scope"],
                "MTD": report["MTD"], "YTD": report["YTD"], "position": report["position"],
                "balance_gap": report["balance_gap"], "departments": len(report["departments"])}, default=str, indent=2))
    print("READ ONLY: no masters, balances, journals, GL or periods changed.")


if __name__ == "__main__":
    main()
