"""Check the Catering migration emits PostgreSQL DDL without touching a database."""
from importlib.util import module_from_spec, spec_from_file_location
from io import StringIO
from pathlib import Path

from alembic.operations import Operations
from alembic.runtime.migration import MigrationContext


def test_receiving_billing_migration_emits_postgresql_schema():
    path = Path(__file__).resolve().parents[1] / "alembic" / "versions" / "20261030_receiving_billing.py"
    spec = spec_from_file_location("migration_receiving_billing_1030", path)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    assert module.down_revision == "20261024_pos_operations"

    statements = StringIO()
    context = MigrationContext.configure(
        url="postgresql://",
        opts={"as_sql": True, "output_buffer": statements},
    )
    with Operations.context(context):
        module.upgrade()
    sql = statements.getvalue().lower()
    for table in ("goods_receipts", "supplier_invoices"):
        assert f"alter table {table}" in sql
    for field in ("shipping_fee_amount", "admin_fee_amount", "other_fee_amount",
                  "shipping_fee_account_id", "admin_fee_account_id",
                  "other_fee_account_id", "other_fee_description",
                  "supplier_document_url", "supplier_document_total",
                  "supplier_invoice_number", "supplier_invoice_date", "supplier_invoice_due_date",
                  "tax_invoice_number", "tax_invoice_date", "discount_amount"):
        assert field in sql
    assert "foreign key" in sql or "references chart_of_accounts" in sql
