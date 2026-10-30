"""Guard the additive supplier billing migration without a production database."""
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect


def test_receiving_billing_migration_adds_supplier_document_and_fee_columns():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261030_receiving_billing.py"
    spec = spec_from_file_location("migration_receiving_billing_1030", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.down_revision == "20261024_pos_operations"

    engine = create_engine("sqlite+pysqlite:///:memory:")
    with engine.begin() as conn:
        for table in ("goods_receipts", "supplier_invoices", "chart_of_accounts"):
            conn.exec_driver_sql(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY)")

        with Operations.context(MigrationContext.configure(conn)):
            module.upgrade()

        receiving_columns = {col["name"] for col in inspect(conn).get_columns("goods_receipts")}
        invoice_columns = {col["name"] for col in inspect(conn).get_columns("supplier_invoices")}
        common = {"shipping_fee_amount", "admin_fee_amount", "other_fee_amount",
                  "shipping_fee_account_id", "admin_fee_account_id",
                  "other_fee_account_id", "other_fee_description", "supplier_document_url",
                  "supplier_document_total"}
        assert common <= receiving_columns
        assert common <= invoice_columns
        assert {"discount_amount", "supplier_invoice_number", "supplier_invoice_date",
                "supplier_invoice_due_date", "tax_invoice_number", "tax_invoice_date"} <= receiving_columns
    engine.dispose()
