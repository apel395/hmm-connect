"""Financial report display setup and automatic period closing evidence."""
from alembic import op
import sqlalchemy as sa

revision = "20261006_financial_reports"
down_revision = "20261004_period_backdates"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "financial_report_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("report_type", sa.String(30), nullable=False, unique=True),
        sa.Column("selected_account_ids", sa.JSON(), nullable=True),
        sa.Column("header_only", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.add_column("fiscal_periods", sa.Column(
        "closing_journal_ids", sa.JSON(), nullable=False, server_default=sa.text("'[]'")))

    # Only new revenue postings use 400. Historical child-account entries are
    # retained and remain readable; migration never rewrites financial amounts.
    conn = op.get_bind()
    revenue = conn.execute(sa.text("SELECT id,account_type FROM chart_of_accounts WHERE account_number='400'")).mappings().first()
    if revenue and revenue["account_type"] not in ("REVENUE", "INCOME"):
        raise RuntimeError("COA 400 exists with a non-revenue type; correct its identity before migration")
    if revenue:
        conn.execute(sa.text("""UPDATE chart_of_accounts SET is_active=true,is_posting=true,
            account_type='REVENUE',normal_balance='CREDIT',financial_statement_group='OPERATING_REVENUE'
            WHERE id=:id"""), {"id":revenue["id"]})
        revenue_id = revenue["id"]
    else:
        revenue_id = conn.execute(sa.text("""INSERT INTO chart_of_accounts
            (account_number,account_name,account_type,normal_balance,account_subtype,
             financial_statement_group,is_posting,is_active,is_system)
            VALUES ('400','Pendapatan','REVENUE','CREDIT','OTHER','OPERATING_REVENUE',true,true,true)
            RETURNING id""")).scalar_one()
    conn.execute(sa.text("""INSERT INTO accounting_settings (setting_key,account_id,description)
        VALUES ('POS_SALES_REVENUE_ACCOUNT',:id,'Single revenue posting account 400')
        ON CONFLICT (setting_key) DO UPDATE SET account_id=EXCLUDED.account_id,
            description=EXCLUDED.description"""), {"id":revenue_id})
    # Choose a unique existing current-year earnings COA; otherwise create a
    # dedicated earnings account. This is earned profit, not an opening contra.
    earnings = conn.execute(sa.text("""SELECT id FROM chart_of_accounts
        WHERE account_type='EQUITY' AND normal_balance='CREDIT' AND is_active=true AND is_posting=true
          AND (lower(account_name) LIKE '%tahun berjalan%' OR lower(account_name) LIKE '%current year%')
          AND NOT EXISTS (SELECT 1 FROM chart_of_accounts child WHERE child.parent_account_id=chart_of_accounts.id)
        ORDER BY id""")).scalars().all()
    configured = conn.execute(sa.text("SELECT id FROM accounting_settings WHERE setting_key='CURRENT_YEAR_EARNINGS_ACCOUNT'")).scalar()
    if not configured:
        if len(earnings) == 1:
            earnings_id = earnings[0]
        else:
            existing = conn.execute(sa.text("SELECT id,account_type,normal_balance,account_name FROM chart_of_accounts WHERE account_number='300-300-100'")).mappings().first()
            if existing and (existing["account_type"] != "EQUITY" or existing["normal_balance"] != "CREDIT" or "tahun berjalan" not in existing["account_name"].lower()):
                raise RuntimeError("COA 300-300-100 is not a current-year earnings account; configure CURRENT_YEAR_EARNINGS_ACCOUNT before migration")
            if existing:
                earnings_id = existing["id"]
                conn.execute(sa.text("UPDATE chart_of_accounts SET is_active=true,is_posting=true WHERE id=:id"), {"id": earnings_id})
            else:
                earnings_id = conn.execute(sa.text("""INSERT INTO chart_of_accounts
                    (account_number,account_name,account_type,normal_balance,account_subtype,
                     financial_statement_group,is_posting,is_active,is_system)
                    VALUES ('300-300-100','Laba Rugi Tahun Berjalan','EQUITY','CREDIT','OTHER','EQUITY',true,true,true)
                    RETURNING id""")).scalar_one()
        conn.execute(sa.text("""INSERT INTO accounting_settings (setting_key,account_id,description)
            VALUES ('CURRENT_YEAR_EARNINGS_ACCOUNT',:id,'Automatic period-close transfer of current-year earnings')"""),
            {"id":earnings_id})

    if sa.inspect(conn).has_table("fiscal_year_close"):
        op.alter_column("fiscal_year_close", "journal_entry_id", existing_type=sa.Integer(), nullable=True)
    else:
        op.create_table("fiscal_year_close",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("fiscal_year", sa.Integer(), nullable=False, unique=True),
            sa.Column("closing_date", sa.Date(), nullable=False),
            sa.Column("journal_entry_id", sa.Integer(), sa.ForeignKey("journal_entries.id"), nullable=True),
            sa.Column("is_closed", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))


def downgrade():
    # Revenue/earnings COAs and mappings may already have real postings; retain.
    op.drop_column("fiscal_periods", "closing_journal_ids")
    op.drop_table("financial_report_settings")
