"""extend legacy import batches and add historical import rows

Revision ID: 20260803_historical_import
Revises: 20260803_product_seed_defaults
"""
from alembic import op
import sqlalchemy as sa

revision = "20260803_historical_import"
down_revision = "20260803_product_seed_defaults"
branch_labels = None
depends_on = None


def upgrade():
    additions = (
        sa.Column("batch_name", sa.String(150)), sa.Column("import_type", sa.String(40)),
        sa.Column("import_mode", sa.String(20), nullable=False, server_default="STRICT"),
        sa.Column("source_type", sa.String(30), nullable=False, server_default="HISTORICAL_IMPORT"),
        sa.Column("period_from", sa.Date()), sa.Column("period_to", sa.Date()),
        sa.Column("file_name", sa.String(255)), sa.Column("original_file_name", sa.String(255)), sa.Column("stored_file_path", sa.String(500)),
        sa.Column("total_rows", sa.Integer(), nullable=False, server_default="0"), sa.Column("valid_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("warning_rows", sa.Integer(), nullable=False, server_default="0"), sa.Column("error_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("imported_rows", sa.Integer(), nullable=False, server_default="0"), sa.Column("failed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("validated_at", sa.DateTime(timezone=True)), sa.Column("notes", sa.Text()),
    )
    for column in additions: op.add_column("import_batches", column)
    op.execute("UPDATE import_batches SET batch_name=COALESCE(description,batch_number), import_type='JOURNAL_ENTRY', created_by_id=imported_by_id")
    op.execute("UPDATE import_batches SET status=CASE status WHEN 'PROCESSING' THEN 'DRAFT' WHEN 'COMPLETED' THEN 'IMPORTED' ELSE status END")
    op.alter_column("import_batches","batch_name",nullable=False);op.alter_column("import_batches","import_type",nullable=False);op.alter_column("import_batches","imported_at",nullable=True)
    op.create_index("ix_import_batches_import_type","import_batches",["import_type"]);op.create_index("ix_import_batches_period","import_batches",["period_from","period_to"]);op.create_index("ix_import_batches_created_by_id","import_batches",["created_by_id"])
    op.create_table("import_rows",
        sa.Column("id",sa.BigInteger(),primary_key=True),sa.Column("import_batch_id",sa.BigInteger(),sa.ForeignKey("import_batches.id",ondelete="CASCADE"),nullable=False),
        sa.Column("row_number",sa.Integer(),nullable=False),sa.Column("sheet_name",sa.String(100)),sa.Column("document_type",sa.String(40),nullable=False),
        sa.Column("raw_data_json",sa.JSON(),nullable=False),sa.Column("normalized_data_json",sa.JSON()),sa.Column("status",sa.String(20),nullable=False,server_default="PENDING"),
        sa.Column("entity_type",sa.String(50)),sa.Column("entity_id",sa.BigInteger()),sa.Column("document_number",sa.String(100)),sa.Column("warning_messages_json",sa.JSON()),sa.Column("error_messages_json",sa.JSON()),
        sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("imported_at",sa.DateTime(timezone=True)))
    op.create_index("ix_import_rows_batch","import_rows",["import_batch_id"]);op.create_index("ix_import_rows_document_type","import_rows",["document_type"]);op.create_index("ix_import_rows_status","import_rows",["status"]);op.create_index("ix_import_rows_entity","import_rows",["entity_type","entity_id"]);op.create_index("ix_import_rows_document_number","import_rows",["document_number"])
    for table in ("purchase_requisitions","purchase_orders","goods_receipts","supplier_invoices","payments","journal_entries"):
        if table in ("supplier_invoices","payments","journal_entries"):op.add_column(table,sa.Column("external_reference",sa.String(100)))
        if table=="journal_entries":op.add_column(table,sa.Column("source_type",sa.String(30),nullable=False,server_default="LIVE"))
        op.add_column(table,sa.Column("import_batch_id",sa.BigInteger(),sa.ForeignKey("import_batches.id",ondelete="SET NULL")));op.add_column(table,sa.Column("imported_by_id",sa.Integer(),sa.ForeignKey("users.id",ondelete="SET NULL")));op.add_column(table,sa.Column("imported_at",sa.DateTime(timezone=True)));op.create_index(f"ix_{table}_import_batch_id",table,["import_batch_id"])
    op.create_index("ix_journal_entries_source_type","journal_entries",["source_type"])


def downgrade():
    op.drop_index("ix_journal_entries_source_type",table_name="journal_entries")
    for table in reversed(("purchase_requisitions","purchase_orders","goods_receipts","supplier_invoices","payments","journal_entries")):
        op.drop_index(f"ix_{table}_import_batch_id",table_name=table);op.drop_column(table,"imported_at");op.drop_column(table,"imported_by_id");op.drop_column(table,"import_batch_id")
        if table=="journal_entries":op.drop_column(table,"source_type")
        if table in ("supplier_invoices","payments","journal_entries"):op.drop_column(table,"external_reference")
    op.drop_table("import_rows")
    for index in ("ix_import_batches_created_by_id","ix_import_batches_period","ix_import_batches_import_type"):op.drop_index(index,table_name="import_batches")
    for column in ("notes","validated_at","created_at","created_by_id","failed_rows","imported_rows","error_rows","warning_rows","valid_rows","total_rows","stored_file_path","original_file_name","file_name","period_to","period_from","source_type","import_mode","import_type","batch_name"):op.drop_column("import_batches",column)
    op.alter_column("import_batches","imported_at",nullable=False)
