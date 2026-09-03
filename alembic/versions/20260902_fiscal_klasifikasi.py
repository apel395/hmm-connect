"""add fiscal classification to fiscal accounts

Revision ID: 20260902_fiscal_klasifikasi
Revises: 20260902_fiscal_coa
"""

from alembic import op
import sqlalchemy as sa

revision = "20260902_fiscal_klasifikasi"
down_revision = "20260902_fiscal_coa"
branch_labels = None
depends_on = None


# Coretax L1-D Jasa: fiscal classification per fiscal account code.
# NORMAL = pass-through; FINAL = taxed finally (excluded from PKP);
# NON_DEDUCTIBLE = expense added back (koreksi positif).
KLASIFIKASI_BY_CODE = {
    "4511": "FINAL",          # Pendapatan Bunga - dikenakan pajak final
    "5321": "NON_DEDUCTIBLE",  # Beban Entertainment - tidak dapat dikurangkan
    "5409": "NON_DEDUCTIBLE",  # Sumbangan - tidak dapat dikurangkan
    "5421": "NON_DEDUCTIBLE",  # Kerugian Selisih Kurs - tidak dapat dikurangkan
}


def upgrade():
    op.add_column(
        "fiscal_accounts",
        sa.Column(
            "klasifikasi_fiskal",
            sa.String(20),
            nullable=False,
            server_default="NORMAL",
        ),
    )
    op.create_index(
        "ix_fiscal_accounts_klasifikasi_fiskal", "fiscal_accounts", ["klasifikasi_fiskal"]
    )
    bind = op.get_bind()
    for code, klasifikasi in KLASIFIKASI_BY_CODE.items():
        bind.execute(
            sa.text(
                "UPDATE fiscal_accounts SET klasifikasi_fiskal = :k WHERE code = :c"
            ),
            {"k": klasifikasi, "c": code},
        )


def downgrade():
    bind = op.get_bind()
    bind.execute(
        sa.text(
            "UPDATE fiscal_accounts SET klasifikasi_fiskal = 'NORMAL' "
            "WHERE code IN ('4511','5321','5409','5421')"
        )
    )
    op.drop_index("ix_fiscal_accounts_klasifikasi_fiskal", table_name="fiscal_accounts")
    op.drop_column("fiscal_accounts", "klasifikasi_fiskal")
