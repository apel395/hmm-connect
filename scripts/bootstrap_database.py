"""Create a fresh HMM Connect schema and align it with Alembic.

This command is only for a brand-new, empty database. Historical migrations in
this recovered repository assume that legacy base tables already exist, so a
fresh installation must create the current SQLAlchemy schema once and stamp the
current Alembic head.
"""

from __future__ import annotations

import argparse

from alembic import command
from alembic.config import Config
from sqlalchemy import Column, MetaData, String, Table, inspect

from app.core.database import engine
from app.models import Base
from app.models.sales_transaction import SalesTransaction  # noqa: F401 - ensure POS/AR FK tables are registered


REQUIRED_TABLES = {
    "products",
    "purchase_orders",
    "roles",
    "suppliers",
    "users",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap an empty HMM Connect database from current models.",
    )
    parser.add_argument(
        "--confirm-empty-database",
        action="store_true",
        help="Required acknowledgement that the target database is new and empty.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.confirm_empty_database:
        raise SystemExit(
            "Refusing to continue. Re-run with --confirm-empty-database only for "
            "a brand-new database with no application data."
        )

    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names(schema="public"))
    if existing_tables:
        listed = ", ".join(sorted(existing_tables))
        raise SystemExit(
            "Refusing to bootstrap a non-empty database. Existing public tables: "
            f"{listed}"
        )

    print(f"Creating {len(Base.metadata.tables)} tables from current models...")
    Base.metadata.create_all(bind=engine)

    created_tables = set(inspect(engine).get_table_names(schema="public"))
    missing = sorted(REQUIRED_TABLES - created_tables)
    if missing:
        raise SystemExit(
            "Schema creation completed but required tables are missing: "
            + ", ".join(missing)
        )

    print("Stamping database at the current Alembic head...")
    Table(
        "alembic_version",
        MetaData(),
        Column("version_num", String(255), primary_key=True),
    ).create(bind=engine, checkfirst=True)
    command.stamp(Config("alembic.ini"), "head")

    final_tables = set(inspect(engine).get_table_names(schema="public"))
    if "alembic_version" not in final_tables:
        raise SystemExit("Alembic stamp completed without creating alembic_version.")

    print(f"Database bootstrap complete. Created {len(final_tables)} tables.")
    print("Use `alembic upgrade head` for all future schema changes.")


if __name__ == "__main__":
    main()
