"""Non-financial statistical Actual/Budget values and header 900."""
from alembic import op
import sqlalchemy as sa
revision = "20261015_statistics"
down_revision = "20261014_asset_policy"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    header = bind.execute(sa.text("SELECT account_type FROM chart_of_accounts WHERE account_number='900'" )).scalar_one_or_none()
    if header and header != "STATISTIC":
        raise RuntimeError("COA 900 already exists with a financial type; review it before migrating")
    op.create_table("statistical_values",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id"), nullable=False),
        sa.Column("period", sa.Date(), nullable=False),
        sa.Column("location_id", sa.Integer(), sa.ForeignKey("locations.id"), nullable=False),
        sa.Column("department_id", sa.Integer(), sa.ForeignKey("departments.id")),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("actual", sa.Numeric(18,4)), sa.Column("budget", sa.Numeric(18,4)),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("updated_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("actual IS NULL OR actual >= 0", name="ck_stat_actual_positive"),
        sa.CheckConstraint("budget IS NULL OR budget >= 0", name="ck_stat_budget_positive"))
    for column in ("account_id", "period", "location_id"):
        op.create_index("ix_statistical_values_"+column, "statistical_values", [column])
    op.create_index("uq_statistical_value_scope", "statistical_values", ["account_id", "period", "location_id", sa.text("coalesce(department_id, 0)")], unique=True)
    if not header:
        bind.execute(sa.text("""INSERT INTO chart_of_accounts (account_number,account_name,account_type,normal_balance,is_posting,is_active,is_system,account_subtype)
            VALUES ('900','Statistik','STATISTIC','DEBIT',false,true,true,'OTHER')"""))


def downgrade():
    if op.get_bind().execute(sa.text("SELECT count(*) FROM statistical_values")).scalar():
        raise RuntimeError("Statistical records exist; export and resolve them before downgrade")
    op.drop_table("statistical_values")
    # Keep 900 and user-configured child metrics; do not delete user configuration.
