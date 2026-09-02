"""add fiscal chart of accounts (Coretax L1-D Jasa)

Revision ID: 20260902_fiscal_coa
Revises: 20260902_sales_transactions
"""

from alembic import op
import sqlalchemy as sa

revision = "20260902_fiscal_coa"
down_revision = "20260902_sales_transactions"
branch_labels = None
depends_on = None


FISCAL_ACCOUNTS = [
    ("1101", "Kas dan Setara Kas", "Aset", False),
    ("1122", "Piutang Usaha - Pihak Ketiga", "Aset", False),
    ("1123", "Piutang Usaha - Pihak yang Mempunyai Hubungan Istimewa", "Aset", False),
    ("1124", "Piutang Lainnya - Pihak Ketiga", "Aset", False),
    ("1125", "Piutang Lainnya - Pihak yang Mempunyai Hubungan Istimewa", "Aset", False),
    ("1131", "Cadangan Kerugian Penurunan Nilai - Aset Lancar", "Aset", False),
    ("1181", "Aset Kontrak", "Aset", False),
    ("1200", "Investasi", "Aset", False),
    ("1401", "Persediaan", "Aset", False),
    ("1421", "Beban Dibayar di Muka", "Aset", False),
    ("1422", "Uang Muka", "Aset", False),
    ("1423", "Pajak Dibayar di Muka", "Aset", False),
    ("1499", "Aset lancar lainnya", "Aset", False),
    ("1501", "Piutang Jangka Panjang", "Aset", False),
    ("1521", "Aset tetap dan inventaris", "Aset", False),
    ("1522", "Dikurangi: Akumulasi penyusutan aset tetap dan inventaris", "Aset", False),
    ("1551", "Investasi pada Perusahaan Asosiasi, Ventura Bersama dan Anak Perusahaan", "Aset", False),
    ("1599", "Investasi Jangka Panjang Lainnya", "Aset", False),
    ("1600", "Aset Tak Berwujud", "Aset", False),
    ("1601", "Dikurangi : Akumulasi Amortisasi-Aset Tak Berwujud", "Aset", False),
    ("1611", "Aktiva Pajak Tangguhan", "Aset", False),
    ("1651", "Klaim atas pengembalian pajak", "Aset", False),
    ("1658", "Cadangan Kerugian Penurunan Nilai - Aset Tidak Lancar", "Aset", False),
    ("1698", "Aset Tidak Lancar Lainnya", "Aset", False),
    ("1700", "Jumlah Aset", "Aset", False),
    ("HDR-360", "[HEADER] Aset Lancar", "Aset", True),
    ("HDR-374", "[HEADER] Aset Tidak Lancar", "Aset", True),
    ("2102", "Utang Usaha - Pihak Ketiga", "Kewajiban", False),
    ("2103", "Utang Usaha - Pihak yang Mempunyai Hubungan Istimewa", "Kewajiban", False),
    ("2111", "Utang Bunga", "Kewajiban", False),
    ("2186", "Liabilitas Kontrak", "Kewajiban", False),
    ("2187", "Liabilitas Sewa Jangka Pendek", "Kewajiban", False),
    ("2191", "Utang Pajak", "Kewajiban", False),
    ("2192", "Utang Dividen", "Kewajiban", False),
    ("2195", "Beban yang Masih Harus Dibayar", "Kewajiban", False),
    ("2201", "Utang Bank Jangka Pendek", "Kewajiban", False),
    ("2202", "Utang Jangka Panjang yang Jatuh Tempo dalam Satu Tahun", "Kewajiban", False),
    ("2203", "Pendapatan Diterima di Muka", "Kewajiban", False),
    ("2228", "Liabilitas Jangka Pendek Lainnya", "Kewajiban", False),
    ("2301", "Utang Bank Jangka Panjang", "Kewajiban", False),
    ("2303", "Utang Jangka Panjang-Pihak Ketiga", "Kewajiban", False),
    ("2304", "Utang Jangka Panjang - Pihak yang Mempunyai Hubungan Istimewa", "Kewajiban", False),
    ("2312", "Liabilitas Sewa Jangka Panjang", "Kewajiban", False),
    ("2321", "Liabilitas Pajak Tangguhan", "Kewajiban", False),
    ("2322", "Liabilitas Imbalan Kerja", "Kewajiban", False),
    ("2998", "Liabilitas Jangka Panjang Lainnya", "Kewajiban", False),
    ("2999", "Jumlah Liabilitas", "Kewajiban", False),
    ("HDR-387", "[HEADER] Liabilitas Jangka Pendek", "Kewajiban", True),
    ("HDR-400", "[HEADER] Liabilitas Jangka Panjang", "Kewajiban", True),
    ("3102", "Modal Saham", "Modal", False),
    ("3120", "Tambahan Modal Disetor", "Modal", False),
    ("3200", "Laba Ditahan", "Modal", False),
    ("3297", "Pendapatan Komprehensif Lainnya", "Modal", False),
    ("3298", "Ekuitas Lainnya", "Modal", False),
    ("3299", "Jumlah Ekuitas", "Modal", False),
    ("3300", "Jumlah Liabilitas dan Ekuitas", "Modal", False),
    ("HDR-409", "[HEADER] Ekuitas", "Modal", True),
    ("5020", "Biaya Pokok Jasa", "Harga Pokok", False),
    ("4021", "Pendapatan Jasa", "Pendapatan", False),
    ("4199", "Pendapatan Usaha Lainnya", "Pendapatan", False),
    ("4501", "Keuntungan Selisih Kurs", "Pendapatan", False),
    ("4503", "Keuntungan Penjualan Aset selain Persediaan", "Pendapatan", False),
    ("4511", "Pendapatan Bunga", "Pendapatan", False),
    ("4599", "Pendapatan Non Usaha Lainnya", "Pendapatan", False),
    ("4600", "Jumlah Pendapatan Non Usaha", "Pendapatan", False),
    ("HDR-437", "[HEADER] Pendapatan Non Usaha", "Pendapatan", True),
    ("5311", "Gaji, Tunjangan, Bonus, Honorarium, THR, dsb", "Beban Usaha", False),
    ("5312", "Beban Imbalan Kerja Lainnya", "Beban Usaha", False),
    ("5313", "Beban Transportasi", "Beban Usaha", False),
    ("5314", "Beban Penyusutan dan Amortisasi", "Beban Usaha", False),
    ("5315", "Beban Sewa", "Beban Usaha", False),
    ("5316", "Beban Bunga", "Beban Usaha", False),
    ("5317", "Beban Sehubungan dengan Jasa", "Beban Usaha", False),
    ("5318", "Beban Penurunan Nilai", "Beban Usaha", False),
    ("5319", "Beban Royalti", "Beban Usaha", False),
    ("5320", "Beban Pemasaran atau Promosi", "Beban Usaha", False),
    ("5321", "Beban Entertainment", "Beban Usaha", False),
    ("5399", "Beban usaha lainnya", "Beban Usaha", False),
    ("5400", "Jumlah Beban Usaha", "Beban Usaha", False),
    ("HDR-422", "[HEADER] Beban Usaha", "Beban Usaha", True),
    ("5405", "Kerugian Penjualan Aset selain Persediaan", "Beban Non Usaha", False),
    ("5409", "Sumbangan", "Beban Non Usaha", False),
    ("5421", "Kerugian Selisih Kurs", "Beban Non Usaha", False),
    ("5499", "Beban Non Usaha Lainnya", "Beban Non Usaha", False),
    ("5500", "Jumlah Beban Non Usaha", "Beban Non Usaha", False),
    ("HDR-443", "[HEADER] Beban Non Usaha", "Beban Non Usaha", True),
]

DEFAULT_MAPPINGS = [
    ("1101", ["100-100-%", "100-110-%", "100-120-%", "100-130-%"]),  # Kas dan Setara Kas
    ("1122", ["100-200-%"]),  # Piutang Usaha - Pihak Ketiga
    ("1124", ["100-210-%"]),  # Piutang Lainnya - Pihak Ketiga
    ("1401", ["100-300-%"]),  # Persediaan
    ("1421", ["100-400-%"]),  # Beban Dibayar di Muka
    ("1423", ["100-500-%"]),  # Pajak Dibayar di Muka
    ("1521", ["100-600-%", "100-700-%", "100-900-%"]),  # Aset tetap dan inventaris
    ("1522", ["100-800-%"]),  # Akumulasi penyusutan
    ("1551", ["101-100-%"]),  # Investasi asosiasi/anak
    ("2102", ["200-100-%"]),  # Utang Usaha - Pihak Ketiga
    ("2103", ["200-600-%"]),  # Utang Usaha - Pihak istimewa
    ("2191", ["200-400-%"]),  # Utang Pajak
    ("2195", ["200-200-%"]),  # Beban yang Masih Harus Dibayar
    ("2203", ["200-500-%"]),  # Pendapatan Diterima di Muka
    ("2228", ["200-300-%"]),  # Liabilitas Jangka Pendek Lainnya
    ("2303", ["200-700-%"]),  # Utang Jangka Panjang
    ("2322", ["200-800-%"]),  # Liabilitas Imbalan Kerja
    ("3102", ["300-100-%"]),  # Modal Saham
    ("4021", ["400-100-%"]),  # Pendapatan Jasa
    ("5020", ["500-100-%"]),  # Biaya Pokok Jasa
    ("5311", ["600-100-%"]),  # Gaji, Tunjangan, Bonus
    ("5399", ["700-500-%", "750-100-%"]),  # Beban usaha lainnya
    ("5316", ["760-100-103", "760-100-104"]),  # Beban Bunga / korporasi
    ("4599", ["760-100-100", "760-100-101", "760-100-102", "760-100-999"]),  # Pendapatan Non Usaha Lainnya
]


def upgrade():
    op.create_table(
        "fiscal_accounts",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(250), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("parent_code", sa.String(20)),
        sa.Column("is_header", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_fiscal_accounts_code", "fiscal_accounts", ["code"])
    op.create_index("ix_fiscal_accounts_category", "fiscal_accounts", ["category"])
    op.create_table(
        "fiscal_account_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fiscal_account_id", sa.Integer(), sa.ForeignKey("fiscal_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commercial_account_id", sa.Integer(), sa.ForeignKey("chart_of_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("fiscal_account_id", "commercial_account_id", name="uq_fiscal_mapping_pair"),
    )
    op.create_index("ix_fiscal_account_mappings_fiscal_account_id", "fiscal_account_mappings", ["fiscal_account_id"])
    op.create_index("ix_fiscal_account_mappings_commercial_account_id", "fiscal_account_mappings", ["commercial_account_id"])

    bind = op.get_bind()
    for i, (code, name, category, is_header) in enumerate(FISCAL_ACCOUNTS, start=1):
        bind.execute(
            sa.text(
                "INSERT INTO fiscal_accounts (code, name, category, is_header, sort_order) "
                "VALUES (:code, :name, :category, :h, :ord)"
            ),
            {"code": code, "name": name, "category": category, "h": is_header, "ord": i},
        )

    for fiscal_code, patterns in DEFAULT_MAPPINGS:
        for pattern in patterns:
            bind.execute(
                sa.text(
                    "INSERT INTO fiscal_account_mappings (fiscal_account_id, commercial_account_id) "
                    "SELECT f.id, c.id FROM fiscal_accounts f, chart_of_accounts c "
                    "WHERE f.code = :fcode AND c.account_number LIKE :ccode "
                    "ON CONFLICT DO NOTHING"
                ),
                {"fcode": fiscal_code, "ccode": pattern},
            )

    op.execute(
        "INSERT INTO permissions (code, description) VALUES ('fiscal.view', 'View Fiscal COA and Mappings'), ('fiscal.manage', 'Manage Fiscal COA and Mappings') ON CONFLICT (code) DO NOTHING"
    )
    for code in ("fiscal.view", "fiscal.manage"):
        op.execute(f"INSERT INTO role_permissions (role_id, permission_id) SELECT role.id, permission.id FROM roles AS role JOIN permissions AS permission ON permission.code = '{code}' WHERE role.name IN ('SYSTEM_ADMINISTRATOR', 'FINANCE', 'GENERAL_MANAGER', 'AUDITOR') ON CONFLICT DO NOTHING")


def downgrade():
    bind = op.get_bind()
    for code in ("fiscal.view", "fiscal.manage"):
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE permission_id IN "
                "(SELECT id FROM permissions WHERE code = :c)"
            ),
            {"c": code},
        )
        bind.execute(
            sa.text("DELETE FROM permissions WHERE code = :c"),
            {"c": code},
        )
    op.drop_table("fiscal_account_mappings")
    op.drop_table("fiscal_accounts")